#!/usr/bin/env python
# coding: utf-8

from tqdm import tqdm
import pickle
import csv
import numpy as np
import sys
import mwparserfromhell as mwph

from utils import wtpGetLinkAnchor
from utils import get_feature_set
from utils import getLinks, normalise_title, normalise_anchor, ngram_iterator

import time

if len(sys.argv) >= 2:
    wiki_id = sys.argv[1]
else:
    wiki_id = "enwiki"

t1 = time.time()

## open dataset-dicts from pickle files
anchors = pickle.load(open("../../data/{0}/{0}.anchors.pkl".format(wiki_id), "rb"))
pageids = pickle.load(open("../../data/{0}/{0}.pageids.pkl".format(wiki_id), "rb"))
redirects = pickle.load(open("../../data/{0}/{0}.redirects.pkl".format(wiki_id), "rb"))
word2vec = pickle.load(open("../../data/{0}/{0}.w2vfiltered.pkl".format(wiki_id), "rb"))

####################
# This scripts extracts examples from the backtesting protocol
# and reduces them to gold triple: (page, mention, link)
# We turn the gold triple into features and generate negatives examples
# Positive example: The correct link
# Negative example: identified mentions and all candidate links

infile = "../../data/{0}/training/sentences_train.csv".format(wiki_id)
outfile = "../../data/{0}/training/link_train.csv".format(wiki_id)

####################
# Bunch of utility function that need to be factored out

####################
# Pre-processing
# Feature extraction is time consuming. Lets track progress with TQDM
# Here I count the number of sentences, just to inform TQDM on what to expect
print("Counting number of sentences..")
lines = 0
with open(infile) as csv_file:
    lines = len(csv_file.readlines())
print("Processing #", lines, " lines")

####################
# Start the extraction
# We write the training samples directly into the outputfile
with open(outfile, "w") as f:
    with open(infile) as csvfile:
        readCSV = csv.reader(csvfile, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in tqdm(readCSV, total=lines):
            if len(row) != 2:
                continue
            page = row[0]
            wikitext = row[1]
            # a link is [[link | text]]

            inp_pairs = getLinks(wikitext, redirects=redirects, pageids=pageids)
            set_inp_pairs = set(inp_pairs.items())

            # get all possible mentions
            wikitext_nolinks = mwph.parse(wikitext).strip_code()
            tested_mentions = set()
            for gram in ngram_iterator(wikitext_nolinks, 10, 1):
                mention = gram.lower()
                mention_original = gram
                # if the mention exist in the DB
                # it was not previously linked (or part of a link)
                # none of its candidate links is already used
                # it was not tested before (for efficiency)
                if mention in anchors and mention not in tested_mentions:
                    tested_mentions.add(mention)
            # we also add the mentions inp_pairs to make sure we have positive examples
            for mention in inp_pairs.keys():
                if mention in anchors:
                    tested_mentions.add(mention)
            # add (mention,link)-pairs as positive or negative examples
            for mention in tested_mentions:
                mention = normalise_anchor(mention)
                candidates_link = anchors[mention]
                for link in candidates_link:
                    link = normalise_title(link)
                    if (mention, link) in set_inp_pairs:
                        label = True
                    else:
                        label = False
                    try:
                        features = get_feature_set(
                            page, mention, link, anchors, word2vec
                        )
                        str_write = "%s\t%s\t%s" % (page, mention, link)
                        for feature in features:
                            str_write += "\t%s" % feature
                        str_write += "\t%s" % label
                        str_write += "\n"
                        f.write(str_write)
                        ## write the data as features
                        ## page text candidate feature1 feature2 ... label
                    except:
                        pass

print("Building the model training dataset is DONE.")
t2 = time.time()
print(t2 - t1)
