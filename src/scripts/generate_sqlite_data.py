import sys
import pickle
from sqlitedict import SqliteDict

if len(sys.argv) >= 2:
    wiki_id = sys.argv[1]
else:
    wiki_id = "enwiki"

list_fname = ["anchors", "pageids", "redirects", "w2vfiltered"]
for fname in list_fname:
    filename = "../../data/{0}/{0}.{1}.pkl".format(wiki_id, fname)
    output_path = "../../data/{0}/{0}.{1}.sqlite".format(wiki_id, fname)
    dict_pkl = pickle.load(open(filename, "rb"))
    sqlite_db = SqliteDict(output_path, autocommit=True)
    for k, v in dict_pkl.items():
        sqlite_db[k] = v
    sqlite_db.close()
