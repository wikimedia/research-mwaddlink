from Levenshtein import jaro as levenshtein_score
from scipy.stats import kurtosis
import requests
import operator
import numpy as np

import urllib.parse as up

import wikitextparser as wtp
import mwparserfromhell
import re

import nltk

######################
# parsing titles
######################


def normalise_title(title):
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


def normalise_anchor(anchor):
    """
    Normalising anchor  (text):
    - strip()
    - lowercase
    Note that we do not do the other normalisations since we want to match the strings from the text
    """
    # anchor = up.unquote(anchor)
    n_anchor = anchor.strip()  # .replace("_", " ")
    return n_anchor.lower()


def wtpGetLinkAnchor(wikilink):
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


def getLinks(wikicode, redirects=None, pageids=None):
    """
    get all links in a page
    """
    link_dict = {}
    linklist = wtp.parse(str(wikicode)).wikilinks
    for l in linklist:
        link, anchor = wtpGetLinkAnchor(l)
        # if redirects is not None, resolve the redirect
        if redirects is not None:
            link = resolveRedirect(link, redirects)
        # if pageids is not None, keep only links appearing as key in pageids
        if pageids is not None:
            if link not in pageids:
                continue
        link_dict[anchor] = link
    return link_dict


def resolveRedirect(link, redirects):
    """
    resolve the redirect.
    check whether in pageids (main namespace)

    """
    return redirects.get(link, link)


# Split a MWPFH node <TEXT> into sentences
def tokenizeSent(text):
    for line in text.split("\n"):
        for sent in nltk.sent_tokenize(line):
            yield sent


def get_tokens(sent):
    """tokenize a sentence.
    keep track of whether there was a whitespace between tokens or not.
    for example, "Berlin, Germany" gets tokenized by nltk as
    ["Berlin", ",", "Germany"].
    this leads to ambiguity when generating strings from ngrams as to whether
    to include whitespace or not.
    here we return ["Berlin", ",", " ", "Germany"]
    """
    tokens = []
    for w in sent.split(" "):
        for w_ in nltk.word_tokenize(w):
            tokens += [w_]
        tokens += [" "]
    # the last token will always be whitespace (can be removed)
    return tokens[:-1]


def get_ngrams(tokens, n):
    """concatenate n non-whitespace tokens"""
    for i_start, w_start in enumerate(tokens):
        if w_start == " ":
            continue
        gram = w_start
        gram_count = 1
        for j in range(i_start, len(tokens) - 1):
            if gram_count == n:
                yield gram
                break
            w = tokens[j + 1]
            gram += w
            if w != " ":
                gram_count += 1


def ngram_iterator(text, gram_length_max, gram_length_min=1):
    """
    iterator yields all n-grams from a text.
    - splits at newline
    - spits sentence
    - tokenizes
    - create string of n tokens for variable n
    """
    lines = text.split("\n")
    for line in lines:
        for sent in tokenizeSent(line):
            for gram_length in range(gram_length_max, gram_length_min - 1, -1):
                tokens = get_tokens(sent)
                for gram in get_ngrams(tokens, gram_length):
                    yield gram


def getPageDict(title: str, wiki_id: str, api_url: str = None) -> dict:
    """
    get the wikitext for a pagetitle for a wiki
    """
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content|ids",
        "rvslots": "main",
        "rvlimit": 1,
        "titles": title,
        "format": "json",
        "formatversion": "2",
    }

    api_url = api_url or "https://{0}.wikipedia.org/w/api.php".format(
        wiki_id.replace("wiki", "").replace("_", "-")
    )
    headers = {"User-Agent": "mwaddlink"}
    req = requests.get(api_url, headers=headers, params=params)
    res = req.json()
    res_page = res["query"]["pages"][0]
    res_rev = res_page["revisions"][0]

    return {
        "page_title": title,
        "wiki_id": wiki_id,
        "wikitext": res_rev["slots"]["main"]["content"],
        "pageid": res_page["pageid"],
        "revid": res_rev["revid"],
    }


##########################
# getting feature-dataset
##########################


def getDistEmb(ent_a, ent_b, embd):
    dst = 0
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
    except BaseException:
        pass
    if np.isnan(dst):
        dst = 0
    return dst


# Return the features for each link candidate in the context of the text and the page


def get_feature_set(page, text, link, anchors, word2vec):
    ngram = len(text.split())  # simple space based tokenizer to compute n-grams
    freq = anchors[text][link]  # How many times was the link use with this text
    ambig = len(anchors[text])  # home many different links where used with this text
    kur = kurtosis(
        sorted(list(anchors[text].values()), reverse=True) + [1] * (1000 - ambig)
    )  # Skew of usage text/link distribution
    w2v = getDistEmb(
        page, link, word2vec
    )  # W2V Distance between the source and target page
    leven = levenshtein_score(text.lower(), link.lower())
    return (ngram, freq, ambig, kur, w2v, leven)


##########################
# evaluation classification
##########################
# Main decision function.
# for a given page X and a piece of text "lipsum".. check all the candidate and make inference
# Returns the most likely candidate according to the pre-trained link model
# If the probability is below a certain threshold, return None
def classify_links(page, text, anchors, word2vec, model, threshold=0.95):
    # start_time = time.time()
    cand_prediction = {}
    # Work with the 10 most frequent candidates
    limited_cands = anchors[text]
    if len(limited_cands) > 10:
        limited_cands = dict(
            sorted(anchors[text].items(), key=operator.itemgetter(1), reverse=True)[:10]
        )
    for cand in limited_cands:
        # get the features
        #         cand_feats = get_feature_set(page, text, cand, anchors, word2vec,pageids)
        cand_feats = get_feature_set(page, text, cand, anchors, word2vec)

        # compute the model probability
        cand_prediction[cand] = model.predict_proba(
            np.array(cand_feats).reshape((1, -1))
        )[0, 1]

    # Compute the top candidate
    top_candidate = max(cand_prediction.items(), key=operator.itemgetter(1))

    # Check if the max probability meets the threshold before returning
    if top_candidate[1] < threshold:
        return None
    # print("--- %s seconds ---" % (time.time() - start_time))
    return top_candidate


# helper class to break out of nested for-loop when reaching set number of recommendations
class MaxRecError(Exception):
    pass


# Actual Linking function
def process_page(
    wikitext,
    page,
    anchors,
    pageids,
    redirects,
    word2vec,
    model,
    threshold=0.8,
    pr=True,
    return_wikitext=True,
    context=10,
    maxrec=-1,
):
    """
    returns updated wikitext
    """
    # parse the wikicode
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
    added_links = []

    # try-except to break out of nested for-loop once we found maxrec links to add
    try:
        for node in page_wikicode_text_nodes:
            # check the offset of the node in the wikitext_init
            node_val = node.value
            i1_node_init = page_wikicode_init.find(node_val)
            i2_node_init = i1_node_init + len(node_val)
            # The ngram_iterator generates substrings from the text of the article to check as candidate-anchors
            # for links. It will do that by concatenating individual word-tokens (roughly speaking everything that
            # is separated by a whitespace) to ngrams (strings that consist of n tokens); for example "Atlantic Ocean"
            # would be a 2-gram. The arguments gram_length_max, gram_length_min define the range in which we vary n
            # The current range n=5,...,1 means we first check all substrings of length 5, then 4, and so on until we
            # reach 1. This range is defined by looking at the typical size of existing links in the anchor-dictionary.
            # There are text-anchors that are not covered by this; they have much larger values for n; however,
            # most anchors have small values of n.
            # Reducing the range of the ngram-iterator we have fewer substrings for which we check the
            # anchor-dictionary (and subsequently other lookups from checking whether to put a link).
            for gram in ngram_iterator(text=node, gram_length_max=5, gram_length_min=1):
                mention = gram.lower()
                mention_original = gram
                # if the mention exist in the DB
                # it was not previously linked (or part of a link)
                # none of its candidate links is already used
                # it was not tested before (for efficiency)
                if (
                    mention in anchors
                    and not any(mention in s for s in linked_mentions)
                    and not bool(set(anchors[mention].keys()) & linked_links)
                    and mention not in tested_mentions
                ):
                    # logic
                    # print("testing:", mention, len(anchors[mention]))
                    candidate = classify_links(
                        page,
                        mention,
                        anchors,
                        word2vec,
                        model,
                        threshold=threshold,
                    )
                    if candidate:
                        candidate_link, candidate_proba = candidate
                        # print(">> ", mention, candidate)
                        ############## Critical ##############
                        # Insert The Link in the current wikitext
                        match = re.compile(
                            r"(?<!\[\[)(?<!-->)\b{}\b(?![\w\s]*[\]\]])".format(
                                re.escape(mention_original)
                            )
                        )
                        new_str = "[[" + candidate_link + "|" + mention_original
                        # add the probability
                        if pr:
                            new_str += "|pr=" + str(candidate_proba)
                        new_str += "]]"
                        newval, found = match.subn(new_str, node.value, 1)
                        node.value = newval
                        ######################################
                        # Book-keeping
                        linked_mentions.add(mention)
                        linked_links.add(candidate_link)
                        if found == 1:
                            page_wikicode_init_substr = page_wikicode_init[
                                i1_node_init:i2_node_init
                            ]
                            i1_sub = page_wikicode_init_substr.lower().find(mention)
                            start_offset = i1_node_init + i1_sub
                            end_offset = start_offset + len(mention)
                            ## provide context of the mention (+/- c characters in substring and wikitext)
                            if context == None:
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
                                    str_context[i1_sub + len(mention_original) : i2_c],
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
                                    str_context[i1_sub + len(mention_original) : i2_c],
                                ]
                            # Find 0-based index of anchor text match in a way that hopefully mostly survives
                            # wikitext -> HTML transformation: count occurrences of the text in top-level
                            # text nodes u
                            preceding_nodes = page_wikicode_text_nodes[
                                : page_wikicode_text_nodes.index(node)
                            ]
                            match_index = sum(
                                str(node).count(mention_original)
                                for node in preceding_nodes
                            ) + page_wikicode_init_substr[:i1_sub].count(
                                mention_original
                            )
                            new_link = {
                                "link_target": candidate_link,
                                "link_text": mention_original,
                                "score": float(candidate_proba),
                                "start_offset": start_offset,
                                "end_offset": end_offset,
                                "match_index": match_index,
                                "context_wikitext": context_wikitext,
                                "context_plaintext": context_substring,
                            }
                            added_links += [new_link]
                            # stop iterating the wikitext to generate link recommendations
                            # as soon as we have maxrec link-recommendations
                            if len(added_links) == maxrec:
                                raise MaxRecError
                    # More Book-keeping
                    tested_mentions.add(mention)
    except MaxRecError:
        pass
    # if yes, we return the adapted wikitext
    # else just return list of links with offsets
    if return_wikitext:
        return page_wikicode
    else:
        return added_links
