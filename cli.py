import argparse
import json
import logging
import json_logging
from sys import stdout
from src.scripts.utils import getPageDict, normalise_title
from src.query import Query

LOG_LEVEL = logging.DEBUG
json_logging.init_non_web(enable_json=True)
logger = logging.getLogger("logger")
logger.setLevel(LOG_LEVEL)
logger.addHandler(logging.StreamHandler(stdout))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--page-title", "-p",
                        default=None,
                        type=str,
                        required=True,
                        help="Page title to use in the query.")

    parser.add_argument("--page-id", "-i",
                        default=None,
                        type=int,
                        required=False,
                        help="Page ID to use in the query.")

    parser.add_argument("--lang", "-l",
                        default=None,
                        type=str,
                        required=True,
                        help="Language (wiki) for which to get recommendations (e.g. enwiki or en)")

    parser.add_argument("--threshold", "-t",
                        default=0.5,
                        type=float,
                        help="Threshold value for links to be recommended")

    args = parser.parse_args()
    lang = args.lang.replace('wiki', '')
    page_title = normalise_title(args.page_title)
    threshold = args.threshold
    page_dict = getPageDict(page_title, lang)
    query = Query(logger)
    dict_result = query.run(
        wikitext=page_dict['wikitext'],
        page_title=page_title,
        pageid=page_dict['pageid'],
        revid=page_dict['revid'],
        threshold=threshold,
        lang=lang
    )
    json_out = json.dumps(dict_result, indent=4)
    logger.info('Recommended links: %s', json_out)
    print(json_out)


if __name__ == '__main__':
    main()
