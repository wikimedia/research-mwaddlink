import pickle
import argparse
from sqlitedict import SqliteDict
from src.mysql import get_mysql_connection, import_model_to_table
import logging
import json_logging
from sys import stdout

LOG_LEVEL = logging.DEBUG
json_logging.init_non_web(enable_json=True)
logger = logging.getLogger("logger")
logger.setLevel(LOG_LEVEL)
logger.addHandler(logging.StreamHandler(stdout))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wiki-id",
        "-id",
        default=None,
        type=str,
        required=True,
        help="Wiki ID to use for copying SQLite files into MySQL.",
    )
    parser.add_argument(
        "--tables",
        "-t",
        nargs="+",
        default=(
            "anchors",
            "redirects",
            "pageids",
            "w2vfiltered",
            "model",
        ),
        required=False,
    )
    table_prefix = "lr"
    args = parser.parse_args()
    wiki_id = args.wiki_id
    mysql_conn = get_mysql_connection()
    cursor = mysql_conn.cursor()
    for table in args.tables:
        logger.info("Populating table %s" % table)

        if table == "model":
            with open(
                "./data/{0}/{0}.linkmodel.json".format(wiki_id), mode="r"
            ) as data:
                import_model_to_table(
                    cursor=cursor, wiki_id=wiki_id, linkmodel=data.read()
                )
        else:
            filename = ("./data/{0}/{0}.%s.sqlite" % table).format(wiki_id)
            sqlitedict = SqliteDict(filename)
            tablename = "%s_%s_%s" % (table_prefix, wiki_id, table)
            cursor.execute("TRUNCATE {table}".format(table=tablename))
            logger.info("Inserting %d items" % len(sqlitedict))
            for key, value in sqlitedict.items():
                query = "INSERT INTO {table} VALUES (%s,%s)".format(table=tablename)
                try:
                    cursor.execute(query, (key, pickle.dumps(value)))
                except BaseException as err:
                    print(err)
        mysql_conn.commit()

    cursor.close()
    mysql_conn.close()


if __name__ == "__main__":
    main()
