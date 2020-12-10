import argparse
from src.mysql import get_mysql_connection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wiki-id",
        "-id",
        default=None,
        type=str,
        required=True,
        help="Wiki ID to use for table creation. Use short form, e.g. 'en' instead of 'enwiki'.",
    )
    parser.add_argument(
        "--tables",
        "-t",
        nargs="+",
        default=[
            "anchors",
            "redirects",
            "pageids",
            "w2vfiltered",
            "model",
        ],
        required=False,
    )
    table_prefix = "lr"

    args = parser.parse_args()
    connection = get_mysql_connection()
    cursor = connection.cursor()

    for table in args.tables:
        if table == "model":
            tablename = "%s_%s" % (table_prefix, table)
        else:
            tablename = "%s_%s_%s" % (table_prefix, args.wiki_id, table)
        create_query = (
            "CREATE TABLE {tablename} ("
            "  `lookup` TEXT NOT NULL,"
            "  `value` LONGBLOB NOT NULL,"
            "  INDEX `lookup_index` (`lookup`)"
            ") CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ).format(tablename=tablename)
        try:
            cursor.execute(create_query)
        except Exception as err:
            print(err)

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
