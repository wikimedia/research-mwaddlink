from sqlitedict import SqliteDict
import argparse
import xgboost as xgb
import sys,os
import json

from scripts.utils import normalise_title
from scripts.utils import getPageDict,process_page
import multiprocessing

PATH_mwaddlink=""

## logging via json
#https://github.com/bobbui/json-logging-python
import json_logging, logging, sys
LOG_LEVEL = logging.DEBUG
# log is initialized without a web framework name
json_logging.init_non_web(enable_json=True)
logger = logging.getLogger("logger")
logger.setLevel(LOG_LEVEL)
logger.addHandler(logging.StreamHandler(sys.stdout))

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--page","-p",
                        default=None,
                        type = str,
                        required=True,
                        help="page-title to get recommendations for")

    parser.add_argument("--lang","-l",
                        default=None,
                        type = str,
                        required=True,
                        help="language (wiki) for which to get recommendations (e.g. enwiki or en)")

    parser.add_argument("--threshold","-t",
                        default=0.5,
                        type = float,
                        help="threshold value for links to be recommended")

    args = parser.parse_args()
    lang = args.lang.replace('wiki','')
    page_title = normalise_title(args.page)
    threshold = args.threshold

    logger.info('Getting link recommendations for article %s in %swiki with link-threshold %s'%(page_title, lang,threshold))
    
    ## open the trained model
    logger.info('Loading the trained model')
    try:
        anchors = SqliteDict(os.path.join(PATH_mwaddlink,"../data/{0}/{0}.anchors.sqlite".format(lang))  )
        pageids = SqliteDict(os.path.join(PATH_mwaddlink,"../data/{0}/{0}.pageids.sqlite".format(lang)))
        redirects = SqliteDict(os.path.join(PATH_mwaddlink,"../data/{0}/{0}.redirects.sqlite".format(lang)) )
        word2vec = SqliteDict(os.path.join(PATH_mwaddlink,"../data/{0}/{0}.w2v.filtered.sqlite".format(lang)) )
        nav2vec = SqliteDict(os.path.join(PATH_mwaddlink,"../data/{0}/{0}.nav.filtered.sqlite".format(lang)) )
        ## load trained model
        n_cpus_max = min([int(multiprocessing.cpu_count()/4),8])
        model = xgb.XGBClassifier(n_jobs =n_cpus_max )  # init model
        model.load_model(os.path.join(PATH_mwaddlink,"../data/{0}/{0}.linkmodel_v2.bin".format(lang)))  # load data
    except:
        # logging
        logger.error('Could not open trained model in %swiki. try another language.'%lang)

    ## querying the API to get the wikitext for the page
    logger.info('Getting the wikitext of the article')
    try:
        page_dict = getPageDict(page_title,lang)
        wikitext = page_dict['wikitext']
        pageid = page_dict['pageid']
        revid = page_dict['revid']
    except:
        wikitext = ""
        logger.error("""Not able to retrieve article '%s' in %swiki. try another article."""%(page_title,lang))

    ## querying the API to get the wikitext for the page
    logger.info('Processing wikitext to get link recommendations')
    try:
        added_links = process_page(wikitext, page_title, anchors, pageids, redirects, word2vec,nav2vec, model, threshold = threshold, return_wikitext = False)
    except:
        logger.error("""Not able to process article '%s' in %swiki. try another article."""%(page_title,lang))

    ## closing model
    try:
        anchors.close()
        pageids.close()
        redirects.close()
        word2vec.close()
        nav2vec.close()
    except:
        logger.warning('Could not close model in %swiki.'%lang)

    
    ## querying the API to get the wikitext for the page
    logger.info('Number of links from recommendation model: %s'%len(added_links))
    if len(added_links) == 0:
        logger.info('Model did not yield any links to recommend. Try a lower link-threshold (e.g. -t 0.2)')

    dict_return = {
        'page_title':page_title,
        'lang':lang,
        'pageid':pageid,
        'revid':revid,
        'no_added_links':len(added_links),
        'added_links':added_links,
    }
    json_out = json.dumps(dict_return, indent=4)
    logger.info('Recommended links: %s',dict_return)
    print('--- Recommended links ---')
    print(json_out)

if __name__ == "__main__":
    main()
