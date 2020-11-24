from sqlitedict import SqliteDict
from src.mysql import get_mysql_connection
import tempfile
from src import MySqlDict
import os


class DatasetLoader:
    def __init__(self, backend="mysql", wiki_id=None, table_prefix="lr"):
        self.backend = backend
        self.wiki_id = wiki_id
        self.table_prefix = table_prefix
        if self.backend == "mysql":
            self.model_path = os.path.join(
                tempfile.gettempdir(), "{0}.linkmodel.json".format(wiki_id)
            )
        else:
            self.model_path = "./data/{0}/{0}.linkmodel.json".format(wiki_id)

    def get(self, tablename=None):
        if self.backend == "mysql":
            return MySqlDict.MySqlDict(
                tablename="%s_%s_%s" % (self.table_prefix, self.wiki_id, tablename),
                conn=get_mysql_connection(),
                datasetname=tablename,
            )
        else:
            return SqliteDict(
                ("./data/{0}/{0}.%s.sqlite" % tablename).format(self.wiki_id)
            )

    def get_model_path(self):
        # The model is a special case.
        # Get the path to the model. If we're using SQLite, it's assumed the model already exists
        # in the data/{wiki_id} directory. If we're using MySQL, check if the model exists in the temp dir
        # and if so return that path, otherwise attempt to load from MySQL, save it to the system temp dir
        # and then return the path.
        if os.path.exists(self.model_path):
            return self.model_path
        elif self.backend == "mysql":
            self._load_model_from_mysql()
            return self.model_path
        else:
            raise RuntimeError("Unable to load model.")

    def _load_model_from_mysql(self):
        cursor = get_mysql_connection().cursor()
        cursor.execute("SELECT value FROM lr_model WHERE lookup = %s", (self.wiki_id,))
        model = cursor.fetchone()
        if model is None:
            raise Exception("Could not load model from MySQL")
        file = open(self.model_path, mode="w")
        output = model[0].decode("utf-8")
        file.write(output)
        file.close()
