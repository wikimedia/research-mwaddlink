import sys
import pickle
import gzip
import shutil
import subprocess
from sqlitedict import SqliteDict

"""
Generate SQLite files from python pickle files.

In addition to SQLite files, gzipped copies are created as well as SHA 256 checksums of the gzipped copies
"""

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
    with open(output_path, "rb") as sqlite:
        with gzip.open("%s.gz" % output_path, "wb") as compressed_sqlite:
            shutil.copyfileobj(sqlite, compressed_sqlite)

    with open("%s.checksum" % output_path, "wb") as checksum_file:
        shasum = subprocess.Popen(
            ["shasum", "-a", "256", "%s.gz" % output_path], stdout=subprocess.PIPE
        )
        checksum_file.writelines(shasum.stdout)
        checksum_file.close()
