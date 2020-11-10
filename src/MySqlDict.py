from collections import UserDict
import pickle
from dotenv import load_dotenv


class MySqlDict(UserDict):
    def __init__(self, tablename=None, conn=None, **kwargs):
        super().__init__(**kwargs)
        load_dotenv()
        self.tablename = tablename
        self.conn = conn
        self.cursor = self.conn.cursor()

    def __len__(self):
        get_len_query = "SELECT COUNT(*) FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_len_query)
        rows = self.cursor.fetchone()
        return rows[0] if rows is not None else 0

    def __bool__(self):
        get_max_query = "SELECT MAX(ROWID) FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_max_query)
        result = self.cursor.fetchone()
        return True if result is not None else False

    def iterkeys(self):
        get_keys_query = "SELECT lookup FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_keys_query)
        for row in self.cursor.fetchall():
            yield row[0]

    def itervalues(self):
        get_values_query = "SELECT value FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_values_query)
        for value in self.cursor.fetchall():
            yield pickle.loads(value[0])

    def iteritems(self):
        get_items_query = "SELECT lookup, value FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_items_query)
        for key, value in self.cursor.fetchall():
            yield key, pickle.loads(value)

    def keys(self):
        return self.iterkeys()

    def values(self):
        return self.itervalues()

    def items(self):
        return self.iteritems()

    def close(self):
        self.cursor.close()
        self.conn.close()

    def __contains__(self, key):
        has_item_query = (
            "SELECT value FROM {tablename} WHERE lookup = %s LIMIT 1".format(
                tablename=self.tablename
            )
        )
        self.cursor.execute(has_item_query, (key,))
        return self.cursor.fetchone() is not None

    def __getitem__(self, key):
        get_item_query = (
            "SELECT value FROM {tablename} WHERE lookup = %s LIMIT 1".format(
                tablename=self.tablename
            )
        )
        self.cursor.execute(get_item_query, (key,))
        item = self.cursor.fetchone()
        if item is None:
            raise KeyError(key)
        return pickle.loads(item[0])
