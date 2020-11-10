import sys, os
import bz2, subprocess
import pickle
from sqlitedict import SqliteDict
import glob
from collections import Counter
import numpy as np

if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = "en"

wiki = lang + "wiki"


## convert pickle dictionaries into sqlite-tables
list_fname = ["anchors", "pageids", "redirects", "w2vfiltered", "navfiltered"]
for fname in list_fname:
    filename = "../../data/{0}/{0}.{1}.pkl".format(lang, fname)
    output_path = "../../data/{0}/{0}.{1}.sqlite".format(lang, fname)
    # ## pass if sqlite already exists
    # if not os.path.isfile(output_path):
    #     continue
    dict_pkl = pickle.load(open(filename, "rb"))
    sqlite_db = SqliteDict(output_path, autocommit=True)
    for k, v in dict_pkl.items():
        sqlite_db[k] = v
    sqlite_db.close()
