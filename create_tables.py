import argparse
from src.mysql import get_mysql_connection


def create_tables(mysql_connection=None, raw_args=None):
    """
    :type mysql_connection: MySQL connection object
    :type raw_args: Arguments for argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Create tables in the database if they do not already exist."
    )
    parser.add_argument(
        "--wiki-id",
        "-id",
        default=None,
        type=str,
        required=False,
        help="Wiki ID to use for table creation. Can be omitted for model and checksum tables.",
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
            "checksum",
        ],
        required=False,
    )
    table_prefix = "lr"

    args = parser.parse_args(raw_args)
    if not mysql_connection:
        mysql_connection = get_mysql_connection()
    with mysql_connection.cursor() as cursor:
        for table in args.tables:
            if table in ["model", "checksum"]:
                tablename = "%s_%s" % (table_prefix, table)
            else:
                tablename = "%s_%s_%s" % (table_prefix, args.wiki_id, table)
            create_query = (
                "CREATE TABLE IF NOT EXISTS {tablename} ("
                "  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "  `lookup` TEXT NOT NULL,"
                "  `value` LONGBLOB NOT NULL,"
                "  INDEX `lookup_index` (`lookup`(767))"
                ") CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
            ).format(tablename=tablename)
            cursor.execute(create_query)


if __name__ == "__main__":
    create_tables()
