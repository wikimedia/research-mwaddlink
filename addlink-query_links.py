from sqlitedict import SqliteDict
import argparse
import xgboost as xgb
import sys,os
import json

from scripts.utils import normalise_title
from scripts.utils import getPageDict,process_page
import multiprocessing

PATH_mwaddlink=""

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
                        default=0.9,
                        type = float,
                        help="threshold value for links to be recommended")

    parser.add_argument("--output","-o",
                        default="",
                        type=str,
                        help="if None, print to terminal, otherwise write result to file")

    args = parser.parse_args()
    lang = args.lang.replace('wiki','')
    page_title = normalise_title(args.page)
    threshold = args.threshold
    output_path = args.output

    try:

        anchors = SqliteDict(os.path.join(PATH_mwaddlink,"data/{0}/{0}.anchors.sqlite".format(lang)) )
        pageids = SqliteDict(os.path.join(PATH_mwaddlink,"data/{0}/{0}.pageids.sqlite".format(lang)) )
        redirects = SqliteDict(os.path.join(PATH_mwaddlink,"data/{0}/{0}.redirects.sqlite".format(lang)) )
        word2vec = SqliteDict(os.path.join(PATH_mwaddlink,"data/{0}/{0}.w2v.filtered.sqlite".format(lang)) )
        nav2vec = SqliteDict(os.path.join(PATH_mwaddlink,"data/{0}/{0}.nav.filtered.sqlite".format(lang)) )
        ## load trained model
        n_cpus_max = min([int(multiprocessing.cpu_count()/4),8])
        model = xgb.XGBClassifier(n_jobs =n_cpus_max )  # init model
        model.load_model(os.path.join(PATH_mwaddlink,"data/{0}/{0}.linkmodel.bin".format(lang)))  # load data
    except:
        print('Link recommendation model not available for %swiki. try another language.'%lang)


    try:
        page_dict = getPageDict(page_title,lang)
        wikitext = page_dict['wikitext']
        pageid = page_dict['pageid']
        revid = page_dict['revid']
    except:
        wikitext = ""
        print("""Not able to retrieve article '%s' in %swiki. try another article."""%(page_title,lang))
    try:
        added_links = process_page(wikitext, page_title, anchors, pageids, redirects, word2vec,nav2vec, model, threshold = threshold, return_wikitext = False)
    except:
        print("""Not able to get links-recommendations  for article '%s' in %swiki. """%(page_title,lang))
    anchors.close()
    pageids.close()
    redirects.close()
    word2vec.close()
    nav2vec.close()
    
    dict_return = {
        'page_title':page_title,
        'lang':lang,
        'pageid':pageid,
        'revid':revid,
        'no_added_links':len(added_links),
        'added_links':added_links,

    }
    json_out = json.dumps(dict_return, indent=4)
    if len(output_path) == 0:
        print(json_out)
    else:
        with open(output_path,'w') as fout:
            fout.write(json_out+'\n')

if __name__ == "__main__":
    main()