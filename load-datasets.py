import argparse
import os
import subprocess
from src.mysql import get_mysql_connection, import_model_to_table
import gzip


def main():
    cli_ok_status = "[OK]"
    parser = argparse.ArgumentParser(
        description="Load datasets from dumped MySQL tables and link model in JSON format into a MySQL database."
    )
    parser.add_argument(
        "--wiki-id",
        "-id",
        default=None,
        type=str,
        required=True,
        help="Wiki ID to use for table export.",
    )
    parser.add_argument(
        "--datasets",
        "-d",
        nargs="+",
        default=["anchors", "redirects", "pageids", "w2vfiltered", "model"],
        required=False,
    )
    parser.add_argument(
        "--path",
        "-p",
        default=None,
        type=str,
        required=True,
        help="""
        Absolute path to the a directory containing datasets to load. The directory should contain the following files:
        lr_{WIKI_ID}_anchors.sql.gz, lr_{WIKI_ID}_pageids.sql.gz, lr_{WIKI_ID}_redirects.sql.gz,
        lr_{WIKI_ID}_w2vfiltered.sql.gz, and {WIKI_ID}.linkmodel.json, along with checksums for each file.
        """,
    )

    def get_dataset_filename(dataset_name):
        if dataset_name == "model":
            dataset_filename = "%s.linkmodel.json" % wiki_id
        else:
            dataset_filename = "%s_%s_%s.sql.gz" % (table_prefix, wiki_id, dataset_name)
        return dataset_filename

    def verify_files_exist(dataset_name):
        print(
            "  ",
            "Verifying file and checksum exists for %s..." % dataset_name,
            end="",
            flush=True,
        )
        dataset_filename = get_dataset_filename(dataset_name)
        dataset_checksum_filename = "%s.checksum" % dataset_filename
        if not os.path.exists(dataset_filename):
            raise FileNotFoundError("Could not find dataset %s" % dataset_filename)
        if not os.path.exists(dataset_checksum_filename):
            raise FileNotFoundError(
                "Could not find checksum %s" % dataset_checksum_filename
            )
        print(cli_ok_status)

    def verify_checksum(dataset_name):
        print("  ", "Verifying checksum for %s..." % dataset_name, end="", flush=True)
        devnull = open(os.devnull, "w")
        result = subprocess.run(
            [
                "shasum",
                "-a",
                "256",
                "-c",
                "%s.checksum" % get_dataset_filename(dataset_name),
            ],
            stdout=devnull,
        )
        if result.returncode != 0:
            raise AssertionError(
                "Failed to verify checksum for %s" % get_dataset_filename(dataset_name)
            )
        print(cli_ok_status)

    table_prefix = "lr"
    args = parser.parse_args()
    wiki_id = args.wiki_id
    datasets = args.datasets
    os.chdir("%s" % args.path)
    print("== Importing datasets (%s) for %s ==" % (", ".join(datasets), wiki_id))
    for dataset in datasets:
        verify_files_exist(dataset)
        verify_checksum(dataset)

    mysql_connection = get_mysql_connection()
    print("== Beginning import. COMMIT happens at the end of all queries ==")

    with mysql_connection.cursor() as cursor:
        for dataset in datasets:
            print("  ", "Processing dataset: %s" % dataset)
            if dataset == "model":
                print("    ", "Inserting link model...", end="", flush=True)
                with open("%s.linkmodel.json" % wiki_id, mode="r") as data:
                    import_model_to_table(
                        # This is a small file (few MB) so calling data.read() is safe
                        cursor=cursor,
                        linkmodel=data.read(),
                        wiki_id=wiki_id,
                    )
                print(cli_ok_status)
            else:
                tablename = "%s_%s_%s" % (table_prefix, args.wiki_id, dataset)
                print(
                    "    ",
                    "Deleting all values from %s..." % tablename,
                    end="",
                    flush=True,
                )
                cursor.execute("DELETE FROM %s" % tablename)
                print(cli_ok_status)
                print(
                    "    ",
                    "Inserting content into %s..." % tablename,
                    end="",
                    flush=True,
                )
                num_rows = 0
                for line in gzip.open(get_dataset_filename(dataset)):
                    if line.strip():
                        num_rows += 1
                        cursor.execute(line)
                print(cli_ok_status)
                print("       %d rows inserted" % num_rows)
            print("    ", "Updating stored checksum...", end="", flush=True)
            with open("%s.checksum" % get_dataset_filename(dataset)) as checksum_file:
                cursor.execute(
                    "DELETE FROM lr_checksum WHERE lookup = %s",
                    ("%s_%s" % (wiki_id, dataset)),
                )
                # checksum file is in the default format output from shasum utility,
                # so it contains the SHA followed by a space and then the filename.
                checksum = checksum_file.readline().split(" ")[0]
                cursor.execute(
                    "INSERT INTO lr_checksum VALUES(%s,%s)",
                    ("%s_%s" % (wiki_id, dataset), checksum),
                )
            print(cli_ok_status)

    print("  ", "Committing...", end="", flush=True)
    mysql_connection.commit()
    mysql_connection.close()
    print(cli_ok_status)


if __name__ == "__main__":
    main()
