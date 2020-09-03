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

pageids = {}
redirects = {}

##################
# dump iteration on each page
# from each page with extract pairs of (link, text)
def process_dump(dump, path):
    for page in dump:
        if page.namespace != 0:
            continue

        page_id = page.id
        page_title = page.title

        ## if page is redirect, we get the rredirected-to title
        if page.redirect:
            page_title_rd = ''
            try:
                linklist = wtp.parse(next(page).text).wikilinks

                link_tmp = linklist[0].title.strip().replace('_', ' ')
                link = link_tmp[0].upper() + link_tmp[1:]
                page_title_rd = link
            except:
                pass
        else:
            page_title_rd = None
        yield page_id, page_title, page_title_rd
    print("Done processing path:", path)

    
##################
# we get two dictionaries
# pageids={page_title:page_id} ## only for non-redirect-pages
# redirects={page_title:page_title_rd}, where page_title_rd is the redirected-to page-title ## onlöy for redirect mpages
pbar = tqdm()
for page_id, page_title, page_title_rd, in mwxml.map(process_dump, paths,threads=20):
    if page_title_rd == None:
        pageids[page_title] = page_id
    elif len(page_title_rd)>0:
        redirects[page_title] = page_title_rd
    else:
        pass
    pbar.update(1)
pbar.close()

print('extraction done.')

##################
# store the dictionaries into the language data folder
output_path = '../data/{0}/{0}.pageids'.format(lang)
with open(output_path+'.pkl', 'wb') as handle:
    pickle.dump(pageids, handle, protocol=pickle.HIGHEST_PROTOCOL)

##################
# store the dictionaries into the language data folder
output_path = '../data/{0}/{0}.redirects'.format(lang)
with open(output_path+'.pkl', 'wb') as handle:
    pickle.dump(redirects, handle, protocol=pickle.HIGHEST_PROTOCOL)