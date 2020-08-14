#!/usr/bin/env python
# coding: utf-8

import xml.sax
import mwparserfromhell
import bz2, subprocess
import pickle
import wikitextparser as wtp
from tqdm import trange, tqdm
import glob
from collections import Counter


import mwxml

# Full latest-articles dump
# This path is for WMF cluster
# Download the dumps otherwise
paths = glob.glob('/mnt/data/xmldatadumps/public/enwiki/latest/enwiki-latest-pages-articles*.xml*.bz2')



####################
# There are a number of todos here

# TODO 1: add a parameter LANG to process any language

# TODO 2: generate a list containing the title of all redirects and disambiguation
# save the list in a pickle to reuse it.
# Maybe, it's good to discard any recommendation pointing to a redirect/disambiguation

# TODO 3: extract the page_id, page_title) mapping file
# It seems that the navigation embeddings are indexed on page_id



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
        linklist = wtp.parse(next(page).text).wikilinks
        for l in linklist:
            try:
                link = l.title.strip().replace('_', ' ')
                text = l.text.strip() if l.text else link
                #print(">>>", text, link, l)
                yield link, text
            except:
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
# e.g., ['wmf', 'wmf', 'wmf'] -> 'wmf':3
print("Compressing the dictionary")
for k,v in tqdm(anchors.items()):
    anchors[k] = dict(Counter(v))

##################
# store the dictionary into the language data folder
with open('../data/en/en.anchors.pkl', 'wb') as handle:
    pickle.dump(anchors, handle, protocol=pickle.HIGHEST_PROTOCOL)
