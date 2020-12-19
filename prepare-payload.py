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
        "--threshold",
        "-t",
        default=0.5,
        type=float,
        required=False,
        help="Threshold to use.",
    )

    args = parser.parse_args()
    page_title = normalise_title(args.page_title)
    page_dict = getPageDict(page_title, args.wiki_id, args.api_url)
    page_dict["threshold"] = args.threshold
    print(json.dumps(page_dict, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
