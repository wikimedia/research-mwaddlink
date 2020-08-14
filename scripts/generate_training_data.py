#!/usr/bin/env python
# coding: utf-8

from tqdm import tqdm
import pickle
import csv
import wikitextparser as wtp
from Levenshtein import distance as levenshtein_distance
import wikipedia2vec
import numpy as np
import sys
from scipy.stats import kurtosis

enanchors = pickle.load( open( "../data/en/en.anchors.pkl", "rb" ) )


####################
# This scripts extracts examples from the backtesting protocol
# and reduces them to gold triple: (page, mention, link)
# We turn the gold triple into features and generate negatives examples
# Positive example: The correct link
# Negative example: A randomly picked link from the list of candidates

infile  = "../data/en/training/sentences_train.csv"
outfile = "../data/en/training/link_train.csv"


####################
# Since we are computing features at this point
# We have to load some intermediary models
# Wikipedia2Vec, Nav2Vec

# Embeddings of Wikipedia entities(not words)
from wikipedia2vec import Wikipedia2Vec
w2file = '../data/en/en.w2v.bin'
word2vec = Wikipedia2Vec.load(w2file)

# Navigation embeddings
import fasttext
navfile = '../data/en/word2vec_enwiki_params-cbow-50-5-0.1-10-5-20.bin'
nav2vec = fasttext.load_model(navfile)

####################
# List of word embedded 'entities'
veclist = set([t.title for t in list(word2vec.dictionary.entities())])


####################
# Bunch of utility function that need to be factored out

# Wikipedia2Vec distance
def getW2VDst(ent_a, ent_b):
    dst = 0
    if ent_a in veclist and ent_b in veclist:
        a = word2vec.get_entity_vector(ent_a)
        b = word2vec.get_entity_vector(ent_b)
        dst = (np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b))
    return dst

# Navigation distance
def getNavDst(ent_a, ent_b):
    dst = 0
    if ent_a in pageid and ent_b in pageid:
        page_a = pageid[ent_a]
        page_b = pageid[ent_b]
        if ent_a in veclist and ent_b in veclist:
            a = nav2vec.get_word_vector(page_a)
            b = nav2vec.get_word_vector(page_b)
            dst = (np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b))
    return dst

# TODO: the navigation model should change to (page_title, vector)
# This piece won't be needed then
# Latest update: we might keep page_id because it's much easier for Nav2vec

csv.field_size_limit(sys.maxsize)
reader = csv.reader(open('../data/en/pageid.csv', 'r'))
pageid = {}
for row in reader:
    k, v = row[0].split('\t')
    pageid[v] = k


# Return the features for each link candidate in the context of the text and the page
# TODO: refactor this piece of code to be the same for training model
def get_feature_set(page, text, link):
    ngram = len(text.split()) # simple space based tokenizer to compute n-grams
    freq = enanchors[text][link] # How many times was the link use with this text 
    ambig = len(enanchors[text]) # home many different links where used with this text
    kur = kurtosis(sorted(list(enanchors[text].values()), reverse = True) + [1] * (1000 - ambig)) # Skew of usage text/link distribution
    w2v = getW2VDst(page, link) # W2V Distance between the source and target page
    nav = getNavDst(page, link) # Nav Distance between the source and target page
    return (ngram, freq, ambig, kur, w2v, nav)



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
                # TODO: add a try/except here?
                true_link = l.title.strip().replace('_',' ')
                text = l.text.strip() if l.text else true_link 
                if text in enanchors:
                    # For each candidate link add a datapoint to the training data 
                    # (the true link is 1, false link is 0)
                    for candidate in enanchors[text].keys():
                        label = True if candidate == true_link else False
                        gram, freq, ambig, kur, w2v, nav = get_feature_set(page, text, candidate)
                        f.write("%s\t%s\t%s\t%d\t%d\t%d\t%f\t%f\t%f\t%s\n" % (page, text, candidate, gram, freq, ambig, kur, w2v, nav, label))

print("Building the model training dataset is DONE.")
