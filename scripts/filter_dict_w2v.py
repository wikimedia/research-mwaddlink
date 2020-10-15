import sys, os
import bz2, subprocess
import pickle
import glob
import numpy as np

if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = 'en'

wiki   = lang+'wiki'


## filter the w2v embedding
FILE_PAGEIDS = "../data/{0}/{0}.pageids.pkl".format(lang)
pageids = pickle.load( open( FILE_PAGEIDS, "rb" ) )

# Embeddings of Wikipedia entities(not words)
from wikipedia2vec import Wikipedia2Vec
w2file = '../data/{0}/{0}.w2v.bin'.format(lang)
word2vec = Wikipedia2Vec.load(w2file)

## filter only vectors from entity in pageids (main namespace, no redirect)
N_kept = 0
word2vec_filter = {}
for title in pageids.keys():
    try:
        vec = word2vec.get_entity_vector(title)
        word2vec_filter[title] = np.array(vec)
        N_kept+=1
    except KeyError:
        pass
## dump as pickle
output_path = '../data/{0}/{0}.w2v.filtered'.format(lang)
with open(output_path+'.pkl', 'wb') as handle:
    pickle.dump(word2vec_filter, handle, protocol=pickle.HIGHEST_PROTOCOL)

# delete unused files
for FILENAME in glob.glob(w2file[:-4]+'*'):
    if 'filter' not in FILENAME:
        os.system('rm -r %s'%FILENAME)