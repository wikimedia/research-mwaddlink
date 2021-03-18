from collections import UserDict
import pickle
from dotenv import load_dotenv


class MySqlDict(UserDict):
    def __init__(self, tablename=None, conn=None, datasetname=None, **kwargs):
        """
        Like SqlDict (https://pypi.org/project/sqldict/), but using MySQL as the backend.

        Uses an in process cache to avoid issuing the same SQL queries.
        :param tablename: The tablename to connect to
        :param conn: The connection object from pymysql
        :param datasetname: The name of the dataset to query
        :param kwargs: Additional arguments (currently unused)
        """
        super().__init__(**kwargs)
        load_dotenv()
        self.tablename = tablename
        self.datasetname = datasetname
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.query_count = 0
        self.query_details = {
            "__len__": 0,
            "__bool__": 0,
            "iterkeys": 0,
            "itervalues": 0,
            "iteritems": 0,
            "__contains__": 0,
            "__getitem__": 0,
            "in_process_cache_access_count": 0,
        }
        self.in_process_cache = {}

    def __len__(self):
        get_len_query = "SELECT COUNT(*) FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_len_query)
        self.query_count += 1
        self.query_details["__len__"] += 1
        rows = self.cursor.fetchone()
        return rows[0] if rows is not None else 0

    def __bool__(self):
        get_max_query = "SELECT MAX(ROWID) FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_max_query)
        self.query_count += 1
        self.query_details["__bool__"] += 1
        result = self.cursor.fetchone()
        return True if result is not None else False

    def iterkeys(self):
        get_keys_query = "SELECT lookup FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_keys_query)
        self.query_count += 1
        self.query_details["iterkeys"] += 1
        for row in self.cursor.fetchall():
            yield row[0]

    def itervalues(self):
        get_values_query = "SELECT value FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_values_query)
        self.query_count += 1
        self.query_details["itervalues"] += 1
        for value in self.cursor.fetchall():
            yield pickle.loads(value[0])

    def iteritems(self):
        get_items_query = "SELECT lookup, value FROM {tablename}".format(
            tablename=self.tablename
        )
        self.cursor.execute(get_items_query)
        self.query_count += 1
        self.query_details["iteritems"] += 1
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
        if key in self.in_process_cache:
            self.query_details["in_process_cache_access_count"] += 1
            return True
        has_item_query = (
            "SELECT value FROM {tablename} WHERE lookup = %s LIMIT 1".format(
                tablename=self.tablename
            )
        )
        self.cursor.execute(has_item_query, (key,))
        self.query_count += 1
        self.query_details["__contains__"] += 1
        item = self.cursor.fetchone()
        if item is not None:
            self.in_process_cache[key] = pickle.loads(item[0])
        return item is not None

    def __getitem__(self, key):
        if key in self.in_process_cache:
            self.query_details["in_process_cache_access_count"] += 1
            return self.in_process_cache[key]
        get_item_query = (
            "SELECT value FROM {tablename} WHERE lookup = %s LIMIT 1".format(
                tablename=self.tablename
            )
        )
        self.cursor.execute(get_item_query, (key,))
        self.query_count += 1
        self.query_details["__getitem__"] += 1
        item = self.cursor.fetchone()
        if item is None:
            raise KeyError(key)
        self.in_process_cache[key] = pickle.loads(item[0])
        return self.in_process_cache[key]
