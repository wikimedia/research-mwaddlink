import argparse
import json
import logging
import json_logging
from sys import stdout
from src.scripts.utils import getPageDict, normalise_title
from src.query import Query
from src.DatasetLoader import DatasetLoader

LOG_LEVEL = logging.DEBUG
json_logging.init_non_web(enable_json=True)
logger = logging.getLogger("logger")
logger.setLevel(LOG_LEVEL)
logger.addHandler(logging.StreamHandler(stdout))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--page-title",
        "-p",
        default=None,
        type=str,
        required=True,
        help="Page title to use in the query.",
    )

    parser.add_argument(
        "--page-id",
        "-i",
        default=None,
        type=int,
        required=False,
        help="Page ID to use in the query.",
    )

    parser.add_argument(
        "--wiki-id",
        "-id",
        default=None,
        type=str,
        required=True,
        help="Wiki ID for which to get recommendations. Use shortform (i.e. en and not enwiki)",
    )

    parser.add_argument(
        "--threshold",
        "-t",
        default=0.5,
        type=float,
        help="Threshold value for links to be recommended",
    )

    parser.add_argument(
        "--database-backend",
        "-db",
        default="mysql",
        type=str,
        choices=["mysql", "sqlite"],
        help="Database backend to use for querying.",
    )

    parser.add_argument(
        "--max-recommendations",
        "-m",
        default=20,
        type=int,
        required=False,
        help="Maximum number of link recommendations to query (set to -1 for all)",
    )

    args = parser.parse_args()
    page_title = normalise_title(args.page_title)
    threshold = args.threshold
    page_dict = getPageDict(page_title, args.wiki_id)
    datasetloader = DatasetLoader(args.database_backend, args.wiki_id)
    query = Query(logger, datasetloader)
    dict_result = query.run(
        wikitext=page_dict["wikitext"],
        page_title=page_title,
        pageid=page_dict["pageid"],
        revid=page_dict["revid"],
        threshold=threshold,
        wiki_id=args.wiki_id,
        max_recommendations=args.max_recommendations,
    )
    json_out = json.dumps(dict_result, indent=4)
    print(json_out)


if __name__ == "__main__":
    main()
