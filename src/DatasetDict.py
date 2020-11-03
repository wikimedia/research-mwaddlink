from collections import UserDict


class DatasetDict(UserDict):
    def __init__(self, tablename=None, **kwargs):
        super().__init__(**kwargs)
        self.tablename = tablename
