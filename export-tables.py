import argparse
from src.mysql import get_connection_dict
import os
import subprocess
import gzip


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wiki-id",
        "-id",
        default=None,
        type=str,
        required=True,
        help="Wiki ID to use for table export.",
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
        ],
        required=False,
    )
    parser.add_argument(
        "--path",
        "-p",
        default=None,
        type=str,
        required=False,
        help="Path to dump the exported MySQL tables to",
    )
    table_prefix = "lr"

    args = parser.parse_args()
    wiki_id = args.wiki_id
    connection_dict = get_connection_dict()
    if args.path:
        dump_path = args.path
    else:
        dump_path = "%s/data/%s" % (
            os.path.dirname(os.path.abspath(__file__)),
            wiki_id,
        )
    os.chdir(dump_path)

    for table in args.tables:
        tablename = "%s_%s_%s" % (table_prefix, wiki_id, table)
        print("Exporting table %s" % tablename)
        filename = "%s.sql.gz" % tablename

        mysqldump_command = [
            "mysqldump",
        ]
        if connection_dict["read_default_file"]:
            mysqldump_command += [
                "--defaults-extra-file=%s" % connection_dict["read_default_file"]
            ]
        mysqldump_command += [
            "--skip-opt",
            "--no-create-info",
            "--skip-extended-insert",
            "--skip-create-options",
            "-u%s" % connection_dict["user"],
        ]

        if connection_dict["password"]:
            mysqldump_command += ["-p%s" % connection_dict["password"]]

        mysqldump_command += [
            "--lock-tables=false",
            "-h",
            connection_dict["host"],
            "--port",
            str(connection_dict["port"]),
            connection_dict["database"],
            tablename,
        ]
        with gzip.open(filename, "wb") as gzip_file:
            mysqldump = subprocess.Popen(
                mysqldump_command, stdout=subprocess.PIPE, bufsize=-1
            )
            gzip_file.writelines(mysqldump.stdout)
            gzip_file.close()

        with open("%s.checksum" % filename, "wb") as checksum_file:
            shasum = subprocess.Popen(
                ["shasum", "-a", "256", filename], stdout=subprocess.PIPE
            )
            checksum_file.writelines(shasum.stdout)
            checksum_file.close()


if __name__ == "__main__":
    main()
