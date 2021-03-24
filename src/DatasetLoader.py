from sqlitedict import SqliteDict
from typing import Tuple
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
            self.mysql_connection = get_mysql_connection()
        else:
            self.model_path = "./data/{0}/{0}.linkmodel.json".format(wiki_id)

    def get(self, tablename=None):
        if self.backend == "mysql":
            return MySqlDict.MySqlDict(
                tablename="%s_%s_%s" % (self.table_prefix, self.wiki_id, tablename),
                conn=self.mysql_connection,
                datasetname=tablename,
            )
        else:
            return SqliteDict(
                ("./data/{0}/{0}.%s.sqlite" % tablename).format(self.wiki_id)
            )

    def get_model_path(self) -> Tuple[str, list]:
        """
        Get the path to the model. If we're using SQLite, it's assumed the model already exists
        in the data/{wiki_id} directory. If we're using MySQL, check if the model exists in the temp dir
        and if so return that path, otherwise attempt to load from MySQL, save it to the system temp dir
        :return:
        A tuple of model path (if model is found) and a list of valid domains (if model not found)
        """
        if os.path.exists(self.model_path):
            return self.model_path, []
        elif self.backend == "mysql":
            return self._load_model_from_mysql()
        else:
            # SQLite backend.
            # TODO: Could generate a list of valid project/subdomain pairs by traversing the
            # /data directory, but as we are not focused on SQLite for production this could
            # be left for a follow-up some day.
            return "", []

    def _load_model_from_mysql(self) -> Tuple[str, list]:
        """
        Obtain the link recommendation model from a MySQL table and write to disk.
        :return:
        A tuple of model path (if model is found) and a list of valid domains (if model not found)
        """
        cursor = self.mysql_connection.cursor()
        cursor.execute("SELECT value FROM lr_model WHERE lookup = %s", (self.wiki_id,))
        model = cursor.fetchone()
        if model is None:
            cursor.execute("SELECT lookup FROM lr_model")
            valid_domains = []
            for domain in cursor.fetchall():
                valid_domains.append(domain[0])
            return "", valid_domains
        file = open(self.model_path, mode="w")
        output = model[0].decode("utf-8")
        file.write(output)
        file.close()
        return self.model_path, []
