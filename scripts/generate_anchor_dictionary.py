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

from utils import wtpGetLinkAnchor, normalise_title

paths = []

if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = 'en'

wiki   = lang+'wiki'

dirpath = '/mnt/data/xmldatadumps/public/{0}/*'.format(wiki)
threads  = 20
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
######################################################
#### get the pageids and redirects dictionaries
######################################################
# dump iteration on each page
# from each page with extract pairs of (link, text)
def process_dump_pageids_redirects(dump, path):
    for page in dump:
        if page.namespace != 0:
            continue
        page_id = page.id
        page_title = normalise_title(page.title)
        ## if page is redirect, we get the rredirected-to title
        if page.redirect:
            page_title_rd = normalise_title(page.redirect)
        else:
            page_title_rd = None
        yield page_id, page_title, page_title_rd
    print("Done processing path:", path)

# we get two dictionaries
# pageids={page_title:page_id} ## only for non-redirect-pages
# redirects={page_title:page_title_rd}, where page_title_rd is the redirected-to page-title ## onlöy for redirect mpages
print('1st pass: getting pageids and redirects tables')
pageids = {}
redirects = {}
pbar = tqdm()
for page_id, page_title, page_title_rd, in mwxml.map(process_dump_pageids_redirects, paths,threads=threads):
    if page_title_rd == None:
        pageids[page_title] = page_id
    elif len(page_title_rd)>0:
        redirects[page_title] = page_title_rd
    else:
        pass
    pbar.update(1)
pbar.close()


print('extraction done.')
print("Number of pages", len(pageids))
print("Number of redirects", len(redirects))


################################################
# dump iteration on each page to get links and anchors
# from each page with extract pairs of (link, text)
#################################################
print('2nd pass: getting all links')
anchors = {}
def process_dump_get_links(dump, path):
    for page in dump:
        if page.redirect or page.namespace != 0:
            continue
        ## parse the wikitext
        wikitext = next(page).text
        try:
            linklist = wtp.parse(wikitext).wikilinks
        except:
            # TODO: log the exception. I've seen some encoding errors.
            continue
        ## for each link get anchortext and link
        for l in linklist:
            try:
                ## extract link and anchor from a wtp-wikilink
                ## this includes some normalisation
                link, anchor = wtpGetLinkAnchor(l)
                ## resolve the redirect of link
                link = redirects.get(link,link)
                ## check if link is in main namespace
                if link in pageids:      
                    yield link, anchor
            except:
                # TODO: log the exception. I've seen some encoding errors.
                continue
    print("Done processing path:", path)
   
##################
# mwxml parallelism
# this might apply to english only
# maybe it's possible to split other dumps to part-files
pbar = tqdm()
for link, text in mwxml.map(process_dump_get_links, paths, threads = threads):
    if text in anchors:
        anchors[text].append(link)
    else:
        anchors[text] = [link]
    pbar.update(1)
pbar.close()
print('extraction done.')
print("Number of anchors", len(anchors))

#####################
## saving everything
## save as pickle as well as shelve-object
####################

# store the dictionaries into the language data folder
output_path = '../data/{0}/{0}.pageids'.format(lang)
shelf_db = shelve.open(output_path)
for k,v in tqdm(pageids.items()):
    shelf_db[k] = v
shelf_db.close()
with open(output_path+'.pkl', 'wb') as handle:
    pickle.dump(pageids, handle, protocol=pickle.HIGHEST_PROTOCOL)

# store the dictionaries into the language data folder
output_path = '../data/{0}/{0}.redirects'.format(lang)
shelf_db = shelve.open(output_path)
for k,v in tqdm(redirects.items()):
    shelf_db[k] = v
shelf_db.close()
with open(output_path+'.pkl', 'wb') as handle:
    pickle.dump(redirects, handle, protocol=pickle.HIGHEST_PROTOCOL)


# turn redundant pairs into Count
# e.g., ['wmf', 'wmf', 'wmf'] -> {'wmf':3}
print("Compressing the dictionary")
for k,v in tqdm(anchors.items()):
    anchors[k] = dict(Counter(v))

##################
output_path = '../data/{0}/{0}.anchors'.format(lang)
# print("Storing the dictionary as Shelve")
# # shelve file will have an additional .db extension
shelf_db = shelve.open(output_path)
for k,v in tqdm(anchors.items()):
    shelf_db[k] = v
shelf_db.close()

##################
# store the dictionary into the language data folder
with open(output_path+'.pkl', 'wb') as handle:
    pickle.dump(anchors, handle, protocol=pickle.HIGHEST_PROTOCOL)
