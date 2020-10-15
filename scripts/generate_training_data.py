#!/usr/bin/env python
# coding: utf-8

from tqdm import tqdm
import pickle
import csv
import wikitextparser as wtp
import numpy as np
import sys
from utils import wtpGetLinkAnchor
from utils import get_feature_set
import time
if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = 'en'

wiki   = lang+'wiki'

t1=time.time()

## open dataset-dicts from pickle files
anchors = pickle.load( open("../data/{0}/{0}.anchors.pkl".format(lang),'rb') ) 
pageids = pickle.load( open("../data/{0}/{0}.pageids.pkl".format(lang),'rb') ) 
redirects = pickle.load( open("../data/{0}/{0}.redirects.pkl".format(lang),'rb') ) 
word2vec = pickle.load( open("../data/{0}/{0}.w2v.filtered.pkl".format(lang),'rb') ) 
nav2vec = pickle.load( open("../data/{0}/{0}.nav.filtered.pkl".format(lang),'rb') ) 

####################
# This scripts extracts examples from the backtesting protocol
# and reduces them to gold triple: (page, mention, link)
# We turn the gold triple into features and generate negatives examples
# Positive example: The correct link
# Negative example: A randomly picked link from the list of candidates

infile  = "../data/{0}/training/sentences_train.csv".format(lang)
outfile = "../data/{0}/training/link_train.csv".format(lang)

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
        readCSV = csv.reader(csvfile, delimiter='\t')
        for row in tqdm(readCSV, total = lines):
            if len(row) != 2:
                continue
            page = row[0]
            # a link is [[link | text]]
            labels = wtp.parse(row[1]).wikilinks
            for l in labels:
                try:
                    true_link, text = wtpGetLinkAnchor(l)
                    ## resolve redirect and check if in main namespace
                    true_link = redirects.get(true_link,true_link)
                    if true_link not in pageids:
                        continue

                    if text in anchors:
                        # For each candidate link add a datapoint to the training data 
                        # (the true link is 1, false link is 0)
                        for candidate in anchors[text].keys():
                            label = True if candidate == true_link else False
                            features = get_feature_set(page, text, candidate, anchors, word2vec, nav2vec)
                            str_write = "%s\t%s\t%s"%(page, text, candidate)
                            for feature in features:
                                str_write+="\t%s"%feature
                            str_write+="\t%s"%label
                            str_write+="\n"
                            f.write(str_write)
                            ## write the data as features
                            ## page text candidate feature1 feature2 ... label
                except:
                    pass

print("Building the model training dataset is DONE.")
t2=time.time()
print(t2-t1)