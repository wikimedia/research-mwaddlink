import argparse
import os
import requests
import shutil
import subprocess
from src.mysql import get_mysql_connection, import_model_to_table
import gzip
from create_tables import main as create_tables


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
    parser.add_argument(
        "--download",
        action="store_true",
        default=False,
        required=False,
        help="""
        Attempt to download datasets from analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/
        If the datasets exist, the dataset checksums are compared with existing datasets stored in the database, if any.
        If the checksums differ, the datasets are downloaded to the directory specified by --path, verified, and loaded.
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
    datasets_to_import = []

    mysql_connection = get_mysql_connection()
    if args.download:
        print(
            "== Attempting to download datasets (%s) for %s =="
            % (", ".join(datasets), wiki_id)
        )
        base_url = (
            "https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/%s"
            % wiki_id
        )
        if not os.path.exists(args.path):
            os.makedirs(args.path)

        for dataset in datasets:
            with requests.get(
                "%s/%s.checksum" % (base_url, get_dataset_filename(dataset))
            ) as remote_checksum:
                if remote_checksum.status_code != 200:
                    raise FileNotFoundError(
                        "Unable to download checksum for %s, aborting!" % dataset
                    )
                # We might not have tables yet for our application. The create tables script will not error
                # if they already exist.
                create_tables(["-id", wiki_id, "-t", dataset])
                # Now compare the checksum with what we have stored in the database, if anything
                with mysql_connection.cursor() as cursor:
                    checksum_query = "SELECT value FROM lr_checksum WHERE lookup = %s"
                    cursor.execute(checksum_query, "%s_%s" % (wiki_id, dataset))
                    result = cursor.fetchone()
                    if (
                        result is not None
                        and str(result[0].decode("utf-8"))
                        == remote_checksum.text.split(" ")[0]
                    ):
                        print(
                            "   Checksum in database matches remote checksum, skipping %s"
                            % dataset
                        )
                        continue
                    if result is None:
                        print("   No checksum found for %s in local database" % dataset)
                    datasets_to_import.append(dataset)
                    # Download the dataset to local directory.
                    local_dataset = "%s/%s" % (args.path, get_dataset_filename(dataset))
                    remote_dataset_url = "%s/%s" % (
                        base_url,
                        get_dataset_filename(dataset),
                    )
                    print(
                        "   Downloading dataset %s..." % remote_dataset_url,
                        end="",
                        flush=True,
                    )
                    with requests.get(
                        remote_dataset_url, stream=True
                    ) as remote_dataset:
                        with open(local_dataset, "wb") as local_dataset_file:
                            shutil.copyfileobj(remote_dataset.raw, local_dataset_file)
                            print(cli_ok_status)
                            local_dataset_checksum = "%s.checksum" % local_dataset
                            with open(
                                local_dataset_checksum, "wt"
                            ) as local_dataset_checksum_file:
                                local_dataset_checksum_file.writelines(
                                    remote_checksum.text
                                )
    else:
        datasets_to_import = datasets

    if not len(datasets_to_import):
        print("All datasets are up-to-date!")
        return

    os.chdir("%s" % args.path)
    print(
        "== Importing datasets (%s) for %s =="
        % (", ".join(datasets_to_import), wiki_id)
    )
    for dataset in datasets_to_import:
        verify_files_exist(dataset)
        verify_checksum(dataset)

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
                remote_checksum = checksum_file.readline().split(" ")[0]
                cursor.execute(
                    "INSERT INTO lr_checksum VALUES(%s,%s)",
                    ("%s_%s" % (wiki_id, dataset), remote_checksum),
                )
            print(cli_ok_status)

    print("  ", "Committing...", end="", flush=True)
    mysql_connection.commit()
    mysql_connection.close()
    print(cli_ok_status)
    print("Finished!")


if __name__ == "__main__":
    main()
