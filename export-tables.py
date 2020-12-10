import argparse
from src.mysql import get_connection_dict
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wiki-id",
        "-id",
        default=None,
        type=str,
        required=True,
        help="Wiki ID to use for table export. Use short form, e.g. 'en' instead of 'enwiki'.",
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
    connection_dict = get_connection_dict()

    for table in args.tables:
        if table == "model":
            tablename = "%s_%s" % (table_prefix, table)
        else:
            tablename = "%s_%s_%s" % (table_prefix, args.wiki_id, table)
        print("Exporting table %s" % tablename)
        if connection_dict["password"] is None:
            password = ""
        else:
            password = "--password %s" % connection_dict["password"]
        mysqldump_command = "mysqldump -u%s %s -h %s --port %s %s %s | gzip > %s" % (
            connection_dict["user"],
            password,
            connection_dict["host"],
            connection_dict["port"],
            connection_dict["database"],
            tablename,
            "%s.sql.gz" % tablename,
        )
        os.system(mysqldump_command)


if __name__ == "__main__":
    main()
