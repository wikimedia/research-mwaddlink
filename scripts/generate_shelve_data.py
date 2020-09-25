import sys, os
import bz2, subprocess
import pickle
import shelve
import glob
from tqdm import trange, tqdm
from collections import Counter
import numpy as np

if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = 'en'

wiki   = lang+'wiki'



## pageids
FILE_PAGEIDS = "../data/{0}/{0}.pageids.pkl".format(lang)
dict_load = pickle.load( open( FILE_PAGEIDS, "rb" ) )
output_path = '../data/{0}/{0}.pageids.db'.format(lang)

shelf_db = shelve.open(output_path)
N_kept = 0
for k,v in dict_load.items():
    shelf_db[k] = v
shelf_db.close()


## redirects
FILE_REDIRECTS = "../data/{0}/{0}.redirects.pkl".format(lang)
dict_load = pickle.load( open( FILE_REDIRECTS, "rb" ) )
output_path = '../data/{0}/{0}.redirects.db'.format(lang)

shelf_db = shelve.open(output_path)
N_kept = 0
for k,v in dict_load.items():
    shelf_db[k] = v
shelf_db.close()
os.system("rm -r %s"%(FILE_REDIRECTS))

## anchors
FILE_ANCHORS = "../data/{0}/{0}.anchors.pkl".format(lang)
dict_load = pickle.load( open( FILE_ANCHORS, "rb" ) )
output_path = '../data/{0}/{0}.anchors.db'.format(lang)

shelf_db = shelve.open(output_path)
N_kept = 0
for k,v in dict_load.items():
    shelf_db[k] = v
shelf_db.close()
os.system("rm -r %s"%(FILE_ANCHORS))


pageids = pickle.load( open( FILE_PAGEIDS, "rb" ) )
# Embeddings of Wikipedia entities(not words)
from wikipedia2vec import Wikipedia2Vec
w2file = '../data/{0}/{0}.w2v.bin'.format(lang)
word2vec = Wikipedia2Vec.load(w2file)

output_path = '../data/{0}/{0}.w2v.filtered.db'.format(lang)
shelf_db = shelve.open(output_path)
N_kept = 0
for title in pageids.keys():
    try:
        vec = word2vec.get_entity_vector(title)
        shelf_db[title] = np.array(vec)
        N_kept+=1
    except KeyError:
        pass
shelf_db.close()
for FILENAME in glob.glob(w2file[:-4]+'*'):
    if 'filter' not in FILENAME:
        os.system('rm -r %s'%FILENAME)


# embeddings from fasttext
import fasttext
navfile = '../data/{0}/{0}.nav.bin'.format(lang)
nav2vec = fasttext.load_model(navfile)

output_path = '../data/{0}/{0}.nav.filtered.db'.format(lang)
shelf_db = shelve.open(output_path)
N_kept = 0
for title in pageids.keys():
    try:
        pid = pageids[title]
        vec = nav2vec.get_word_vector(str(pid))
        shelf_db[title] = np.array(vec)
        N_kept+=1
    except KeyError:
        pass
shelf_db.close()

for FILENAME in glob.glob(navfile[:-4]+'*'):
    if 'filter' not in FILENAME:
        os.system('rm -r %s'%FILENAME)
os.system('rm -r %s'%(FILE_PAGEIDS))