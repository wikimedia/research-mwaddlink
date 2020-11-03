from sqlitedict import SqliteDict
from src import DatasetDict


class DatasetLoader:
    def __init__(self, backend='mysql', lang=None):
        self.backend = backend
        self.lang = lang

    def get(self, tablename=None):
        if self.backend == 'mysql':
            return DatasetDict.DatasetDict(tablename=tablename)
        else:
            return SqliteDict(
                ("./data/{0}/{0}.%s.sqlite" % tablename).format(self.lang)
            )
