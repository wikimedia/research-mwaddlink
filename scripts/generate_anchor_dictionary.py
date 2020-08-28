#!/usr/bin/env python
# coding: utf-8

import sys, os
import mwparserfromhell
import bz2, subprocess
import pickle
import shelve
import wikitextparser as wtp
import glob
import mwxml

from tqdm import trange, tqdm
from collections import Counter


# Full latest-articles dump
# This path is for WMF cluster
# Download the dumps otherwise

####################
paths = []

if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = 'en'

wiki   = lang+'wiki'

dirpath = '/mnt/data/xmldatadumps/public/{0}/*'.format(wiki)

# Get the penultimate dump directory (the dir "latest" can have some simlink issues")
try:
    files = glob.glob(dirpath)
    files.sort(key=os.path.getmtime)
    for f in files:
        if 'latest' in f:
            files.remove(f)
            break
    snapshot = files[-1].split('/')[-1]
except:
    snapshot = 'latest'
    
dump_fn = '/mnt/data/xmldatadumps/public/{0}/{1}/{0}-{1}-pages-articles.xml.bz2'.format(wiki,snapshot)
for infile in glob.glob('/mnt/data/xmldatadumps/public/{0}/{1}/{0}-{1}-pages-articles*.xml*.bz2'.format(wiki,snapshot) ):
    if infile == dump_fn:
        continue
    if 'multistream' in infile:
        continue
    paths += [infile]
if len(paths) == 0:
    paths+=[dump_fn]

print("Processing the following Wikipedia dump files:")
for p in paths:
    print(p)

####################
# There are a number of todos here

# TODO 1: generate a list containing the title of all redirects and disambiguation
# save the list in a pickle to reuse it.
# Maybe, it's good to discard any recommendation pointing to a redirect/disambiguation

# TODO 2: extract the (page_id, page_title) mapping file
# It seems that the navigation embeddings are indexed on page_id

# TODO 3: deal with special links (categories, files, etc.)
# deal with this using a fixed list of actual links in Wikipedia (enwiki-latest-all-titles-in-ns0.gz)

# TODO 4: compute the frequency of dictionary entries

# TODO 5: Ideally.. change this whole process to Spark and work with mediawiki_wikitext



####################
# Main data structure
# This is the dictionary to populate
# an example entry:
# anchor['WMF'] = 
# {'.wmf': 3,
#  'Category:2019 in Australian sport': 1,
#  'Category:October 2019 sports events in Australia': 1,
#  'Category:Radio stations in Texas': 1,
#  'WMF Group': 5,
#  'Waco F series': 1,
#  'Wikimedia Foundation': 1,
#  'Windhoeker Maschinenfabrik': 1,
#  'Windows Media Format': 3,
#  'Windows Metafile': 45,
#  'World Minifootball Federation': 3,
#  'World Monuments Fund': 1,
#  'World Muay Thai Federation': 3,
#  'World Muaythai Federation': 5,
#  'Württembergische Metallwaren Fabrik': 2,
#  'Württembergische Metallwarenfabrik': 10}

anchors = {}

##################
# dump iteration on each page
# from each page with extract pairs of (link, text)
def process_dump(dump, path):
    for page in dump:
        if page.redirect or page.namespace != 0:
            continue
        try:
            linklist = wtp.parse(next(page).text).wikilinks
        except:
            # TODO: log the exception. I've seen some encoding errors.
            continue
        for l in linklist:
            try:
                link_tmp = l.title.strip().replace('_', ' ')
                link = link_tmp[0].upper() + link_tmp[1:]
                text = l.text.strip() if l.text else link_tmp
                yield link, text
            except:
                # TODO: log the exception. I've seen some encoding errors.
                continue
    print("Done processing path:", path)

    
##################
# mwxml parallelism
# this might apply to english only
# maybe it's possible to split other dumps to part-files
pbar = tqdm()
for link, text in mwxml.map(process_dump, paths):
    if text in anchors:
        anchors[text].append(link)
    else:
        anchors[text] = [link]
        pbar.update(1)
pbar.close()

print('extraction done.')
print("Number of anchors", len(anchors))

##################
# turn redundant pairs into Count
# e.g., ['wmf', 'wmf', 'wmf'] -> {'wmf':3}
print("Compressing the dictionary")
for k,v in tqdm(anchors.items()):
    anchors[k] = dict(Counter(v))

##################
output_path = '../data/{0}/{1}.{0}.anchors'.format(lang, snapshot)

print("Storing the dictionary as Shelve")
# shelve file will have an additional .db extension
shelf_db = shelve.open(output_path)
for k,v in tqdm(anchors.items()):
    shelf_db[k] = v
shelf_db.close()

##################
# store the dictionary into the language data folder
with open(output_path+'.pkl', 'wb') as handle:
    pickle.dump(anchors, handle, protocol=pickle.HIGHEST_PROTOCOL)
