#!/usr/bin/env python

from mwparserfromhell.nodes import Wikilink, Text, Tag
import wikitextparser as wtp
import re
from tqdm import tqdm
import sys
import random

from mwparserfromhell import parse
import glob
import mwxml

paths = []
if len(sys.argv) >= 2:
    wiki_id = sys.argv[1]
else:
    wiki_id = "enwiki"

## number of sentences to extract
if len(sys.argv) >= 3:
    LIMIT_SENTS = int(sys.argv[2])
else:
    LIMIT_SENTS = 200000  # adhoc

dirpath = "/mnt/data/xmldatadumps/public/{0}/*".format(wiki_id)

# Get the penultimate dump directory (the dir "latest" can have some simlink issues")
try:
    files = glob.glob(dirpath)
    files.sort(key=os.path.getmtime)
    for f in files:
        if "latest" in f:
            files.remove(f)
            break
    snapshot = files[-1].split("/")[-1]
except:
    snapshot = "latest"

dump_fn = "/mnt/data/xmldatadumps/public/{0}/{1}/{0}-{1}-pages-articles.xml.bz2".format(
    wiki_id, snapshot
)
for infile in glob.glob(
    "/mnt/data/xmldatadumps/public/{0}/{1}/{0}-{1}-pages-articles*.xml*.bz2".format(
        wiki_id, snapshot
    )
):
    if infile == dump_fn:
        continue
    if "multistream" in infile:
        continue
    paths += [infile]
if len(paths) == 0:
    paths += [dump_fn]

print("Processing the following Wikipedia dump files:")
for p in paths:
    print(p)

####################
# TODO: We need to make sure that we are extracting fully formed sentences, for any lang/script

# THESE ARE NOT YET USED.
####################
# bunch of helper functions (factor out ?)

# def remove_images(prs):
#     img = re.compile('(File|Image|Category):', re.IGNORECASE)
#     remove_img = [f for f in prs.ifilter_wikilinks() if img.match(str(f.title))]
#     for f in remove_img:
#         prs.remove(f)

# def remove_headings(prs):
#     remove_img = list(prs.ifilter_headings())
#     for f in remove_img:
#         prs.remove(f)


# def pre_filter(text):
#     res = []

#     parts = text.split('\n')
#     # exclude lists and headings
#     excluded_chars = ['*', '=']
#     for p in parts:
#         if p[:1] in excluded_chars:
#             continue

#         # exclude files
#         if '[File:' in p:
#             continue

#         parts = p.split('|')
#         if len(parts) > 1:
#             if parts[0] == 'thumb':
#                 continue

#         # passed everything, append to results
#         res.append(p)

#     return '\n'.join(res)


# def wiki2sents(text, token_min_length=2, token_max_length=20, lower=False):
#     """Parses wikipedia text and returns a list of sentences
#     """
#     prs = text

#     # images aren't removed so remove them manually
#     remove_images(prs)
#     # also remove headings
#     remove_headings(prs)

#     # remove all wikipedia markup code
#     raw = prs.strip_code()

#     # convert to lowercase?
#     if lower:
#         raw = raw.lower()

#     #print(raw)
#     sents = sent_tokenize(prs)
#     res = []
#     for s in sents:
#         if '\n' in s:
#             # chances are it's a list or it's still got a heading or something so skip
# #           print(u'Skipping <{}> because it\'s got new lines so it\'s probably a list'.format(s))
#             continue
#         res.append(s)
# #       print(u'<{}>'.format(s))
#     return res


####################
# Remove links to special content
regexes = [
    "\|.*",
    "\s+",
    "!.*",
    ".*JPG\|",
    ".*jpg\|",
    ".*\}\}",
    ".*\{\{",
    ".*<ref",
    ".*png",
]
combined = "(" + ")|(".join(regexes) + ")"


##################
# Main function to iterate over a page and find fully formed sentences.
# this uses wikitext parser (wtp) and (MWPH)
# TODO: this is essentially a best effort. maybe using Parsoid will solve this headache. ?!
def linked_sents_extractor(title, wikicode):
    # An approximate solution to identify sentences, without a sentence tokenizer

    # bengali has special character for full stop https://en.wikipedia.org/wiki/Bengali_language
    # replace by .\n to ensure that sentence gets split (problems with \w{3,} in bengali script)
    wikicode = wikicode.replace("।", ".\n")
    try:
        filter_wtp = re.sub(r"<\s*ref.*(<\s*/ref\s*>|/\s*>)", "", wikicode)
        wtp_code = wtp.parse(filter_wtp)
        filter_wtp = re.sub(
            r"(\w{3,}[\]\]]*\s*\.\s)|()\n",
            "\\1[cut]",
            wtp_code.plain_text(replace_wikilinks=False, replace_templates=False),
        )
    except:
        return None
        # print("Error on page", title)
    filter_wtp = filter_wtp.split("[cut]")
    sents = []
    # filters
    for a in filter_wtp:
        a = a.strip()
        if not re.match(combined, a) and len(re.findall("\.", a)) == 1:
            sents.append(a)
    for j in sents:
        jmwp = parse(j)
        check = True
        for i in jmwp.nodes:
            if not (isinstance(i, Wikilink) or isinstance(i, Text)):
                check = False
        # preserve sentences that have at least a link
        if check and len(jmwp.nodes) > 2 and len(jmwp.filter_wikilinks()) > 0:
            return j  # j is the sentence
    return None


##################
# dump iteration on each page
# from each page with extract pairs of (link, sentence with links)
def process_dump(dump, path):
    for page in dump:
        if page.redirect or page.namespace != 0:
            continue
        code = next(page).text
        if not page.title.startswith("Wikipedia:"):
            # yield linked_sents_extractor(page.title, code)
            sent = linked_sents_extractor(page.title, code)
            if sent:
                yield page.title, sent


##################
# Global variables
# TODO: if necessary, parametrize the script to take these as input
count = 0
# LIMIT_SENTS = 200000 ## see above
# Storage array of sentences
wiki_links = []


##################
# mwxml parallelism
# this might apply to english only
# maybe it's possible to split other dumps to part-files
pbar = tqdm(total=LIMIT_SENTS)
for title, sentence in mwxml.map(process_dump, paths, threads=10):
    wiki_links.append((title, sentence))
    count += 1
    if count >= LIMIT_SENTS:
        break
    pbar.update(1)
pbar.close()
print("number of sentences extracted", len(wiki_links))


##################
# store two files
# training: to be used by the generate_training_data.py, because in the future we might want to use the whole sentence.
# test: this is effectively the data used by the backtesting protocol.
LIMIT_SENTS_SPLIT = len(wiki_links) // 2
print(LIMIT_SENTS_SPLIT)

wiki_links_indices = list(range(len(wiki_links)))
# reproducible shuffling
random.seed(2)
# shuffle order of extracted sentences when spliting into training/test
random.shuffle(wiki_links_indices)

# Store the sentences for training
with open("../../data/{0}/training/sentences_train.csv".format(wiki_id), "w") as f:
    for i in wiki_links_indices[:LIMIT_SENTS_SPLIT]:
        row = wiki_links[i]
        f.write("%s\n" % "\t".join(row))

# Store the sentences for back-testing
with open("../../data/{0}/testing/sentences_test.csv".format(wiki_id), "w") as f:
    for i in wiki_links_indices[LIMIT_SENTS_SPLIT:]:
        row = wiki_links[i]
        f.write("%s\n" % "\t".join(row))
