import operator
import re
import time

from src.MySqlDict import MySqlDict

import urllib.parse as up
from collections.abc import Generator
from typing import Any, cast

import mwparserfromhell  # type: ignore[import-untyped]
import numpy as np
import wikitextparser as wtp  # type: ignore[import-untyped]
import xgboost
from Levenshtein import jaro as levenshtein_score
from mwtokenizer import Tokenizer  # type: ignore[import-untyped]
from mwtokenizer.config.symbols import (  # type: ignore[import-untyped]
    ALL_UNICODE_PUNCTUATION,
)
from scipy.stats import kurtosis  # type: ignore[import-untyped]


from src.scripts.ngram_utils import (
    get_ngrams,
    get_tokens,
    tokenize_sentence,
)

FREQUENCY = 10


class MentionRegexException(Exception):
    status_code = 400

    def __init__(self, mention: str, wikitext: str):
        super().__init__()
        self.message = f'Unable to find match for "{mention}" in "{wikitext}"'

    def to_dict(self) -> dict[str, str]:
        return {"message": self.message}


######################
# parsing titles
######################


def normalise_title(title: str) -> str:
    """
    Normalising title (links)
    - deal with quotes
    - strip()
    - '_'--> ' '
    - capitalize first letter
    """
    title = up.unquote(title)
    title = title.strip()
    if len(title) > 0:
        title = title[0].upper() + title[1:]
    n_title = title.replace("_", " ")
    if "#" in n_title:
        n_title = n_title.split("#")[0]
    return n_title


def normalise_anchor(anchor: str) -> str:
    """
    Normalising anchor  (text):
    - strip()
    - lowercase
    Note that we do not do the other normalisations since we want to match the strings
    from the text
    """
    # anchor = up.unquote(anchor)
    n_anchor = anchor.strip()  # .replace("_", " ")
    return n_anchor.lower()


def wtpGetLinkAnchor(wikilink: wtp.WikiLink) -> tuple[str, str]:
    """
    extract anchor and link from a wikilink from wikitextparser.
    normalise title and anchor
    """
    # normalise the article title (quote, first letter capital)
    link_tmp = wikilink.title
    link = normalise_title(link_tmp)
    # normalise the anchor text (strip and lowercase)
    anchor_tmp = wikilink.text if wikilink.text else link_tmp
    anchor = normalise_anchor(anchor_tmp)
    return link, anchor


def getLinks(
    wikicode: str,
    redirects: dict[str, str] | None = None,
    pageids: dict[str, int] | None = None,
) -> dict[str, str]:
    """
    get all links in a page
    """
    link_dict = {}
    linklist = wtp.parse(str(wikicode)).wikilinks
    for lnk in linklist:
        link, anchor = wtpGetLinkAnchor(lnk)
        # if redirects is not None, resolve the redirect
        if redirects is not None:
            link = resolveRedirect(link, redirects)
        # if pageids is not None, keep only links appearing as key in pageids
        if pageids is not None:
            if link not in pageids:
                continue
        link_dict[anchor] = link
    return link_dict


def resolveRedirect(link: str, redirects: dict[str, str]) -> str:
    """
    resolve the redirect.
    check whether in pageids (main namespace)

    """
    return redirects.get(link, link)


def ngram_iterator(
    text: str, tokenizer: Tokenizer, gram_length_max: int, gram_length_min: int = 1
) -> Generator[str, None, None]:
    """
    iterator yields all n-grams from a text.
    - splits at newline
    - spits sentence
    - tokenizes
    - create string of n tokens for variable n
    """
    for sent in tokenize_sentence(text, tokenizer):
        tokens = get_tokens(sent, tokenizer)
        for gram_length in range(gram_length_max, gram_length_min - 1, -1):
            yield from get_ngrams(tokens, gram_length)


def getDistEmb(ent_a: str, ent_b: str, embd: dict[str, list[float]]) -> float:
    dst = 0.0
    try:  # try if entities are in embd
        a = embd[ent_a]
        b = embd[ent_b]
        norm_ab = np.linalg.norm(b) * np.linalg.norm(a)
        # if norm of any vector is 0, we assign dst=0 (maximum dst)
        if norm_ab == 0:
            dst = 0.0
        else:
            dst = np.dot(a, b) / norm_ab
    #         dst = (np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b))
    except KeyError:
        # Embedding not found, ignore key
        pass
    except Exception as e:
        print("ERROR: ", type(e).__name__, e)
        pass
    if np.isnan(dst):
        dst = 0
    return dst


def get_feature_set(
    page: str,
    text: str,
    link: str,
    anchors: dict[str, dict[str, int]],
    word2vec: dict[str, list[float]],
    wiki_id: str,
    tokenizer: Tokenizer,
) -> tuple[int, int, float, float, float, float, str]:
    ngram = list(tokenizer.word_tokenize(text, use_abbreviation=True))  # tokenize text
    ngram = list(
        filter(lambda x: not x.startswith(" "), ngram)
    )  # could be a single or multiple spaces that needs to be removed
    ngram = list(
        filter(lambda x: x not in ALL_UNICODE_PUNCTUATION, ngram)
    )  # remove punctuation
    ngram_len = len(ngram)
    freq = anchors[text][link]  # How many times was the link use with this text
    ambig = len(anchors[text])  # home many different links where used with this text
    kur = kurtosis(
        sorted(list(anchors[text].values()), reverse=True) + [1] * (1000 - ambig)
    )  # Skew of usage text/link distribution
    w2v = getDistEmb(
        page, link, word2vec
    )  # W2V Distance between the source and target page
    leven = levenshtein_score(text.lower(), link.lower())
    return (ngram_len, freq, ambig, float(kur), float(w2v), float(leven), wiki_id)


##########################
# evaluation classification
##########################
# Main decision function.
# For a given page X and a piece of text "lipsum".. check all the candidate and make
# inference. Returns the most likely candidate according to the pre-trained link model.
# If the probability is below a certain threshold, return None
def classify_links(
    page: str,
    text: str,
    anchors: dict[str, dict[str, int]],
    word2vec: dict[str, list[float]],
    model: xgboost.XGBClassifier,
    wiki_id: str,
    tokenizer: Tokenizer,
    threshold: float = 0.95,
) -> tuple[str, float] | None:
    # start_time = time.time()
    cand_prediction = {}
    # Work with the `FREQUENCY` most frequent candidates
    limited_cands = anchors[text]
    if len(limited_cands) > FREQUENCY:
        limited_cands = dict(
            sorted(anchors[text].items(), key=operator.itemgetter(1), reverse=True)[:10]
        )
    for cand in limited_cands:
        # get the features
        ngram, freq, ambig, kur, w2v, leven, wiki_id = get_feature_set(
            page, text, cand, anchors, word2vec, wiki_id, tokenizer
        )
        cand_feats = (
            ngram,
            freq,
            ambig,
            kur,
            w2v,
            leven,
            0.0,
        )

        # compute the model probability
        cand_prediction[cand] = model.predict_proba(
            np.array(cand_feats).reshape((1, -1))
        )[0, 1]

    # Compute the top candidate
    if not cand_prediction:
        return None
    top_candidate = max(cand_prediction.items(), key=operator.itemgetter(1))

    # Check if the max probability meets the threshold before returning
    if top_candidate[1] < threshold:
        return None
    # print("--- %s seconds ---" % (time.time() - start_time))
    return top_candidate


# helper class to break out of nested for-loop when reaching set number of
# recommendations
class MaxRecError(Exception):
    pass


# Helper class to break out of page processing loop when maximum page processing time
# has been reached.
class MaxTimeError(Exception):
    pass


# Actual Linking function
def process_page(  # noqa: PLR0915, PLR0912
    wikitext: str,
    page: str,
    anchors: dict[str, dict[str, int]],
    pageids: dict[str, int],
    redirects: dict[str, str],
    word2vec: dict[str, list[float]],
    model: xgboost.XGBClassifier,
    wiki_id: str,
    language_code: str,
    threshold: float = 0.8,
    pr: bool = True,
    return_wikitext: bool = True,
    context: int = 10,
    maxrec: int = -1,
    sections_to_exclude: list[str] | None = None,
) -> dict[str, Any] | mwparserfromhell.wikicode.Wikicode:
    """
    Recommend links for a given wikitext.

    :param str wikitext: Page source
    :param str page: Page title
    :param dict anchors: Anchor dataset for the wiki
    (link text -> {link target title -> frequency})
    :param dict pageids: Pageid dataset for the wiki (title -> id)
    :param dict redirects: Redirect dataset for the wiki
    (original title -> redirect target)
    :param dict word2vec: word2vec dataset for the wiki (word -> vector)
    :param xgboost.XGBClassifier model: The wiki's model for predicting link targets
    for words.
    :param string language_code: The ISO 639 language code to use with processing.
    :param float threshold: Minimum probability score required to include a prediction
    :param bool pr: Whether to include probability scores in the wikitext as 'pr' link
    parameters.
    :param bool return_wikitext: Whether to return wikitext or data.
    :param int context: The number of characters before/after the link to include when
    returning data.
    :param int maxrec: Maximum number of recommendations to return (-1 for unlimited)
    :param list sections_to_exclude: List of section names to exclude from link
    suggestion generation, e.g. "References"
    :return: When return_wikitext is true, return updated wikitext with the new links
    added (or pseudo-wikitext with the custom 'pr' parameters if pr=True).
    Otherwise, return a data structure suitable for returning from the API.
    :rtype: string or dict
    """
    from icu import Locale, UnicodeString  # type: ignore[import-untyped]

    if sections_to_exclude is None:
        sections_to_exclude = []
    sections_to_exclude_nocase = list(
        section.casefold() for section in sections_to_exclude
    )
    tokenizer = Tokenizer(language_code=language_code)

    response = {"links": cast(list[dict[str, Any]], []), "info": ""}
    init_time = time.time()
    # Give ourselves a one second buffer to return the response after the
    # configured timeout limit has been reached.
    max_page_process_time_buffer = 1
    max_page_process_time = 30 - max_page_process_time_buffer
    page_wikicode = mwparserfromhell.parse(wikitext)

    page_wikicode_init = str(page_wikicode)  # save the initial state
    page_wikicode_text_nodes = page_wikicode.filter_text(recursive=False)

    # get all existing links
    dict_links = getLinks(
        page_wikicode, redirects=redirects, pageids=pageids
    )  # get all links, resolve redirects
    linked_mentions = set(dict_links.keys())
    linked_links = set(dict_links.values())
    # include also current pagetitle
    linked_mentions.add(normalise_anchor(page))
    linked_links.add(normalise_title(page))

    tested_mentions = set()

    # try-except to break out of nested for-loop once we found maxrec links to add
    try:
        for section in page_wikicode.get_sections(
            include_lead=True, include_headings=True, flat=True
        ):
            if not section:
                # This means the section is empty; one instance where this occurs
                # is in articles that have no lead and instead begin with a section
                # heading
                continue
            # Special-handling for lead section, which doesn't have a name.
            if (
                not isinstance(section.nodes[0], mwparserfromhell.nodes.heading.Heading)
                and "%LEAD%" in sections_to_exclude
            ):
                continue

            section_heading = str(section.nodes[0].title).strip()
            if section_heading.casefold() in sections_to_exclude_nocase:
                continue
            for node in section.filter_text(recursive=False):
                mentions = {}
                # check the offset of the node in the wikitext_init
                node_val = node.value
                i1_node_init = page_wikicode_init.find(node_val)
                i2_node_init = i1_node_init + len(node_val)
                # The ngram_iterator generates substrings from the text of the article
                # to check as candidate-anchors for links. It will do that by
                # concatenating individual word-tokens to ngrams (strings that consist
                # of n tokens); for example "Atlantic Ocean" would be a 2-gram.
                # The arguments gram_length_max, gram_length_min define the range
                #  in which we vary n The current range n=5,...,1 means we first check
                # all substrings of length 5, then 4, and so on until we reach 1.
                # This range is defined by looking at the typical size of existing
                # links in the anchor-dictionary. There are text-anchors that are not
                # covered by this; they have much larger values for n; however, most
                # anchors have small values of n. Reducing the range of the
                # ngram-iterator we have fewer substrings for which we check the
                # anchor-dictionary (and subsequently other lookups from checking
                # whether to put a link).
                grams = ngram_iterator(
                    text=node,
                    tokenizer=tokenizer,
                    gram_length_max=5,
                    gram_length_min=1,
                )
                for gram in grams:
                    if time.time() > init_time + max_page_process_time:
                        response["info"] = (
                            "Stopping page processing as maximum processing time "
                            f"{max_page_process_time + max_page_process_time_buffer}"
                            "seconds reached"
                        )
                        raise MaxTimeError
                    mentions[gram.lower()] = gram

                if not mentions:
                    continue

                if isinstance(anchors, MySqlDict):
                    anchors_with_mentions = anchors.filter(list(mentions))
                    if not anchors_with_mentions:
                        continue
                else:
                    # SQLite will not batch its queries.
                    anchors_with_mentions = anchors

                for mention, mention_original in mentions.items():
                    if (
                        # if the mention exist in the DB
                        mention in anchors_with_mentions
                        # it was not previously linked (or part of a link)
                        and not any(mention in s for s in linked_mentions)
                        # none of its candidate links is already used
                        and not bool(
                            set(anchors_with_mentions[mention].keys()) & linked_links
                        )
                        # it was not tested before (for efficiency)
                        and mention not in tested_mentions
                    ):
                        # logic
                        # print("testing:", mention, len(anchors[mention]))
                        candidate = classify_links(
                            page,
                            mention,
                            anchors_with_mentions,
                            word2vec,
                            model,
                            wiki_id,
                            tokenizer,
                            threshold=threshold,
                        )
                        if candidate:
                            candidate_link, candidate_proba = candidate
                            # print(">> ", mention, candidate)
                            ############## Critical ##############
                            # Insert The Link in the current wikitext
                            mention_regex = re.compile(
                                rf"(?<!\[\[)(?<!-->){re.escape(mention_original)}(?![\w\s]*[\]\]])"
                            )
                            mention_regex_i = re.compile(
                                mention_regex.pattern, re.IGNORECASE
                            )
                            new_str = "[[" + candidate_link + "|" + mention_original
                            # add the probability
                            if pr:
                                new_str += "|pr=" + str(candidate_proba)
                            new_str += "]]"
                            newval, found = mention_regex.subn(new_str, node.value, 1)
                            node.value = newval
                            ######################################
                            # Book-keeping
                            linked_mentions.add(mention)
                            linked_links.add(candidate_link)
                            if found == 1:
                                page_wikicode_init_substr = page_wikicode_init[
                                    i1_node_init:i2_node_init
                                ]
                                # Handle lower-casing of characters in some languages,
                                # e.g. in Azeri, İnsan should be lowercased to insan,
                                # but the default lower-casing in python will change
                                # the İ to an i with two dots.
                                page_wikicode_init_substr_lower = str(
                                    UnicodeString(page_wikicode_init_substr).toLower(
                                        Locale(language_code)
                                    )
                                )
                                match = mention_regex_i.search(
                                    page_wikicode_init_substr_lower
                                )
                                if match is None:
                                    raise MentionRegexException(
                                        mention, page_wikicode_init_substr_lower
                                    )
                                i1_sub = match.start()
                                start_offset = i1_node_init + i1_sub
                                end_offset = start_offset + len(mention)
                                # provide context of the mention (+/- c characters in
                                # substring and wikitext)
                                if context is None:
                                    context_wikitext = mention_original
                                    context_substring = mention_original
                                else:
                                    ## context substring
                                    str_context = page_wikicode_init_substr
                                    i1_c = max([0, i1_sub - context])
                                    i2_c = min(
                                        [
                                            len(str_context),
                                            i1_sub + len(mention_original) + context,
                                        ]
                                    )
                                    context_substring = [
                                        str_context[i1_c:i1_sub],
                                        str_context[
                                            i1_sub + len(mention_original) : i2_c
                                        ],
                                    ]
                                    ## wikitext substring
                                    str_context = wikitext
                                    i1_c = max([0, start_offset - context])
                                    i2_c = min(
                                        [
                                            len(str_context),
                                            end_offset + context,
                                        ]
                                    )
                                    context_wikitext = [
                                        str_context[i1_c:i1_sub],
                                        str_context[
                                            i1_sub + len(mention_original) : i2_c
                                        ],
                                    ]
                                # Find 0-based index of anchor text match in a way that
                                # hopefully mostly survives wikitext to HTML
                                # transformation: count occurrences of the text
                                # in top-level text nodes u
                                preceding_nodes = page_wikicode_text_nodes[
                                    : page_wikicode_text_nodes.index(node)
                                ]
                                match_index = sum(
                                    str(node).count(mention_original)
                                    for node in preceding_nodes
                                ) + page_wikicode_init_substr[:i1_sub].count(
                                    mention_original
                                )
                                new_link: dict[str, Any] = {
                                    "link_target": candidate_link,
                                    "link_text": mention_original,
                                    "score": float(candidate_proba),
                                    "start_offset": start_offset,
                                    "end_offset": end_offset,
                                    "match_index": match_index,
                                    "context_wikitext": context_wikitext,
                                    "context_plaintext": context_substring,
                                }
                                prev_links = list(response["links"])
                                prev_links.append(new_link)
                                response["links"] = prev_links
                                # stop iterating the wikitext to generate link
                                # recommendations as soon as we have maxrec
                                # link-recommendations
                                if len(response["links"]) == maxrec:
                                    response["info"] = (
                                        "Stopping page processing as max "
                                        "recommendations limit {maxrec} reached."
                                    )
                                    raise MaxRecError
                        # More Book-keeping
                        tested_mentions.add(mention)
    except (MaxRecError, MaxTimeError) as e:
        print("ERROR: ", type(e).__name__, e)
        pass
    # if yes, we return the adapted wikitext
    # else just return list of links with offsets
    if return_wikitext:
        return page_wikicode
    else:
        return response
