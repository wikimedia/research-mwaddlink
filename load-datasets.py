import argparse
import os
import requests
import random
import string
import shutil
import subprocess
from src.mysql import get_mysql_connection, import_model_to_table
import gzip
from create_tables import create_tables

ANALYTICS_BASE_URL = os.getenv(
    "ANALYTICS_BASE_URL",
    "https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/",
)


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
        required=False,
        help="""
        Wiki ID to use for loading datasets. If it is not provided, all datasets in the directory specified by the
        --path argument will be loaded. If the --download flag is passed, then this script will attempt to download
        and import all datasets present on
        https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/.
        """,
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
        Absolute path to the a directory containing datasets to load, for example "/srv/app/data/cswiki".
        The directory should contain the following files:
        lr_{WIKI_ID}_anchors.sql.gz, lr_{WIKI_ID}_pageids.sql.gz, lr_{WIKI_ID}_redirects.sql.gz,
        lr_{WIKI_ID}_w2vfiltered.sql.gz, and {WIKI_ID}.linkmodel.json, along with checksums for each file.

        If the --wiki-id argument is not passed, then this should be an absolute path to a parent directory in which the
        per-wiki datasets reside, e.g. "/srv/app/data" instead of "/srv/app/data/cswiki"

        If --download parameter is set, then --path is the directory where the datasets will be downloaded to. In
        production deployment that is currently a temporary location in /tmp/datasets
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

    def cache_bust_url_query_params():
        return {
            "cache_bust": (
                "".join(
                    random.choice(string.ascii_lowercase + string.digits)
                    for _ in range(8)
                ),
            )
        }

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

    def ensure_table_exists(dataset_name_for_table, connection, wiki_id_for_table=None):
        """
        Check to see if a table exists, if not, create it using the standard schema
        used for all tables the link recommendation service utilizes.
        :param dataset_name_for_table:
        :param connection: A MySQL connection object
        :param wiki_id_for_table:
        """
        message_prefix = "[general]"
        if wiki_id_for_table:
            message_prefix = "[%s]" % wiki_id_for_table
        print(
            "  ",
            "%s Ensuring %s table exists..." % (message_prefix, dataset_name_for_table),
            end="",
            flush=True,
        )
        table_args = []
        if wiki_id_for_table:
            table_args += ["-id", wiki_id_for_table]
        table_args += ["--tables", dataset_name_for_table]
        create_tables(raw_args=table_args, mysql_connection=connection)
        print(cli_ok_status)

    def verify_checksum(dataset_name):
        print("  ", "Verifying checksum for %s..." % dataset_name, end="", flush=True)
        devnull = open(os.devnull, "w")
        checksum_verification_result = subprocess.run(
            [
                "shasum",
                "-a",
                "256",
                "-c",
                "%s.checksum" % get_dataset_filename(dataset_name),
            ],
            stdout=devnull,
        )
        if checksum_verification_result.returncode != 0:
            raise AssertionError(
                "Failed to verify checksum for %s" % get_dataset_filename(dataset_name)
            )
        print(cli_ok_status)

    table_prefix = "lr"
    checksum_table = "%s_checksum" % table_prefix
    args = parser.parse_args()
    all_datasets_url = requests.compat.urljoin(ANALYTICS_BASE_URL, "wikis.txt")
    if not args.wiki_id:
        with requests.get(
            all_datasets_url,
            cache_bust_url_query_params(),
        ) as all_datasets_req:
            wiki_ids = list(filter(None, all_datasets_req.text.split("\n")))
    else:
        wiki_ids = [args.wiki_id]

    datasets = args.datasets
    datasets_to_import = []

    print("== Initializing ==")
    with get_mysql_connection() as mysql_connection:
        ensure_table_exists(
            dataset_name_for_table="checksum", connection=mysql_connection
        )
        ensure_table_exists(dataset_name_for_table="model", connection=mysql_connection)
        for wiki_id in wiki_ids:
            for dataset in datasets:
                ensure_table_exists(
                    dataset_name_for_table=dataset,
                    connection=mysql_connection,
                    wiki_id_for_table=wiki_id,
                )

        print("  ", "Beginning process to load datasets for %s" % ", ".join(wiki_ids))

        for wiki_id in wiki_ids:
            # Start a transaction for each wiki. COMMIT happens after all datasets for the wiki have been updated.
            mysql_connection.begin()
            local_dataset_directory = "%s/%s" % (args.path, wiki_id)
            if args.download:
                print(
                    "== Attempting to download datasets (%s) for %s =="
                    % (", ".join(datasets), wiki_id)
                )
                base_url = requests.compat.urljoin(ANALYTICS_BASE_URL, wiki_id)

                if not os.path.exists(local_dataset_directory):
                    os.makedirs(local_dataset_directory)

                for dataset in datasets:
                    with requests.get(
                        "%s/%s.checksum" % (base_url, get_dataset_filename(dataset)),
                        cache_bust_url_query_params(),
                    ) as remote_checksum:
                        if remote_checksum.status_code != 200:
                            raise RuntimeError(
                                "Unable to download checksum for %s, status code: %s."
                                % (dataset, remote_checksum.status_code)
                            )

                        # Now compare the checksum with what we have stored in the database, if anything
                        with mysql_connection.cursor() as cursor:
                            checksum_query = (
                                "SELECT value FROM {checksum_table} WHERE lookup = %s"
                            ).format(checksum_table="%s_checksum" % table_prefix)
                            cursor.execute(
                                checksum_query,
                                ("%s_%s" % (wiki_id, dataset),),
                            )
                            result = cursor.fetchone()
                            if (
                                result is not None
                                and str(result[0].decode("utf-8"))
                                == remote_checksum.text.split(" ")[0]
                            ):
                                print(
                                    "   Checksum in database matches remote checksum, skipping download for %s"
                                    % dataset
                                )
                                continue
                            if result is None:
                                print(
                                    "   No checksum found for %s in local database, will attempt to download"
                                    % dataset
                                )
                            datasets_to_import.append(dataset)
                            # Download the dataset to local directory.
                            local_dataset = "%s/%s" % (
                                local_dataset_directory,
                                get_dataset_filename(dataset),
                            )
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
                                remote_dataset_url,
                                stream=True,
                                params=cache_bust_url_query_params(),
                            ) as remote_dataset:
                                if remote_dataset.status_code != 200:
                                    raise RuntimeError(
                                        "Unable to download dataset from %s, status code: %s."
                                        % (
                                            remote_dataset_url,
                                            remote_checksum.status_code,
                                        )
                                    )
                                with open(
                                    local_dataset, "wt" if dataset == "model" else "wb"
                                ) as local_dataset_file:
                                    if dataset == "model":
                                        local_dataset_file.write(remote_dataset.text)
                                    else:
                                        shutil.copyfileobj(
                                            remote_dataset.raw, local_dataset_file
                                        )
                                    print(cli_ok_status)
                                    local_dataset_checksum = (
                                        "%s.checksum" % local_dataset
                                    )
                                    with open(
                                        local_dataset_checksum, "wt"
                                    ) as local_dataset_checksum_file:
                                        local_dataset_checksum_file.writelines(
                                            remote_checksum.text
                                        )
            else:
                datasets_to_import = datasets

            if not len(datasets_to_import):
                print("  ", "All datasets for %s are up-to-date!" % wiki_id)
                continue

            os.chdir("%s" % local_dataset_directory)
            print(
                "== Importing datasets (%s) for %s =="
                % (", ".join(datasets_to_import), wiki_id)
            )
            for dataset in datasets_to_import:
                verify_files_exist(dataset)
                verify_checksum(dataset)

            with mysql_connection.cursor() as cursor:
                for dataset in datasets_to_import:
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
                        tablename = "%s_%s_%s" % (table_prefix, wiki_id, dataset)
                        print(
                            "    ",
                            "Deleting all values from %s..." % tablename,
                            end="",
                            flush=True,
                        )
                        cursor.execute(
                            "DELETE FROM {tablename}".format(tablename=tablename)
                        )
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
                                # Skip the boilerplate comments at top of the dump file.
                                if line.find(b"INSERT INTO") == -1:
                                    continue
                                num_rows += 1
                                # Hack for b/c with older datasets that do not have (lookup, value)
                                # TODO Remove once all datasets have been regenerated with id column
                                if b"(lookup, value)" not in line:
                                    line_start = line[0 : line.find(b"` VALUES (") + 2]
                                    line_end = line[line.find(b"` VALUES (") + 1 : -1]
                                    line = bytes(
                                        line_start + b"(lookup, value)" + line_end
                                    )
                                cursor.execute(line)
                        print(cli_ok_status)
                        print("       %d rows inserted" % num_rows)
                    print("    ", "Updating stored checksum...", end="", flush=True)
                    with open(
                        "%s.checksum" % get_dataset_filename(dataset)
                    ) as checksum_file:
                        cursor.execute(
                            "DELETE FROM {checksum_table} WHERE lookup = %s".format(
                                checksum_table=checksum_table
                            ),
                            ("%s_%s" % (wiki_id, dataset),),
                        )
                        # checksum file is in the default format output from shasum utility,
                        # so it contains the SHA followed by a space and then the filename.
                        remote_checksum = checksum_file.readline().split(" ")[0]
                        cursor.execute(
                            "INSERT INTO {checksum_table} (lookup, value) VALUES(%s,%s)".format(
                                checksum_table=checksum_table
                            ),
                            (
                                "%s_%s" % (wiki_id, dataset),
                                remote_checksum,
                            ),
                        )
                    print(cli_ok_status)

                print("  ", "Committing...", end="", flush=True)
                mysql_connection.commit()
                print(cli_ok_status)
                print("  ", "Finished importing for %s!" % wiki_id)

        print("Finished importing datasets for %s" % ", ".join(wiki_ids))


if __name__ == "__main__":
    main()
