import argparse
import json
from src.scripts.utils import getPageDict, normalise_title


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
        required=False,
        help="Threshold to use.",
    )

    args = parser.parse_args()
    page_title = normalise_title(args.page_title)
    page_dict = getPageDict(page_title, args.wiki_id)
    page_dict["wiki_id"] = page_dict["lang"]
    # TODO: In a follow-up, convert getPageDict to use "wiki_id" and "page_title".
    del page_dict["lang"]
    page_dict["page_title"] = page_dict["pagetitle"]
    del page_dict["pagetitle"]
    page_dict["threshold"] = args.threshold
    print(json.dumps(page_dict, indent=4))


if __name__ == "__main__":
    main()
