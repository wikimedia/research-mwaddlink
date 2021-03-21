import argparse
import json
import logging
from sys import stdout
from src.scripts.utils import normalise_title
from src.MediaWikiApi import MediaWikiApi
from src.query import Query
from src.DatasetLoader import DatasetLoader

LOG_LEVEL = logging.DEBUG
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
        help="Wiki ID for which to get recommendations.",
    )

    parser.add_argument(
        "--api-url",
        default=None,
        type=str,
        required=False,
        help="Full URL to api.php.",
    )

    parser.add_argument(
        "--proxy-api-url",
        default=None,
        type=str,
        required=False,
        help="Full URL to a proxy to api.php.",
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
    mw_api = MediaWikiApi(api_url=args.api_url, proxy_api_url=args.proxy_api_url)
    page_dict = mw_api.get_article(page_title, args.wiki_id)
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
    json_out = json.dumps(dict_result, indent=4, ensure_ascii=False)
    print(json_out)


if __name__ == "__main__":
    main()
