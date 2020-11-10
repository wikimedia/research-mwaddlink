import sys, os
import bz2, subprocess
import pickle
import glob
import numpy as np
import fasttext

if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = "en"

wiki = lang + "wiki"

## filter the embeddings and save as sqlite-tables
FILE_PAGEIDS = "../../data/{0}/{0}.pageids.pkl".format(lang)
pageids = pickle.load(open(FILE_PAGEIDS, "rb"))


# embeddings from fasttext
navfile = "../../data/{0}/{0}.nav.bin".format(lang)
nav2vec = fasttext.load_model(navfile)

N_kept = 0
nav2vec_filter = {}
for title in pageids.keys():
    try:
        pid = pageids[title]
        vec = nav2vec.get_word_vector(str(pid))
        nav2vec_filter[title] = np.array(vec)
        N_kept += 1
    except KeyError:
        pass

output_path = "../../data/{0}/{0}.navfiltered".format(lang)
## dump as pickle
with open(output_path + ".pkl", "wb") as handle:
    pickle.dump(nav2vec_filter, handle, protocol=pickle.HIGHEST_PROTOCOL)

## filter old files
for FILENAME in glob.glob(navfile[:-4] + "*"):
    if "filter" not in FILENAME:
        os.system("rm -r %s" % FILENAME)
