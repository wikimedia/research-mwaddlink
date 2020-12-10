import argparse
import multiprocessing
import pickle

import mwparserfromhell as mwph
import pandas as pd
import xgboost as xgb

from utils import getLinks
from utils import process_page

"""
backtesting evlauation of trained model on held-out testset
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lang",
        "-l",
        default=None,
        type=str,
        required=True,
        help="language (wiki) for which to get recommendations (e.g. enwiki or en)",
    )

    parser.add_argument(
        "--nmax",
        "-nmax",
        default=-1,
        type=int,
        help="maximum number of sentences to evaluate",
    )

    parser.add_argument(
        "--threshold",
        "-t",
        default=None,
        type=float,
        help="threshold value for links to be recommended (set if you want to evaluate for specific threshold-value, if not specified, will evaluate for a range 0.0, 0.1, ..., 0.9",
    )

    # parser.add_argument("--nint","-nint",
    #                     default=1000,
    #                     type = int,
    #                     help ="report prec and recall every nint testing-samples")

    args = parser.parse_args()
    lang = args.lang.replace("wiki", "")
    threshold = args.threshold
    N_max = args.nmax
    # N_interval = args.nint

    ## open dataset-dicts from pickle files
    anchors = pickle.load(open("../../data/{0}/{0}.anchors.pkl".format(lang), "rb"))
    pageids = pickle.load(open("../../data/{0}/{0}.pageids.pkl".format(lang), "rb"))
    redirects = pickle.load(open("../../data/{0}/{0}.redirects.pkl".format(lang), "rb"))
    word2vec = pickle.load(
        open("../../data/{0}/{0}.w2vfiltered.pkl".format(lang), "rb")
    )

    ## load trained model
    ## use a fourth of the cpus, at most 8
    n_cpus_max = min([int(multiprocessing.cpu_count() / 4), 8])
    model = xgb.XGBClassifier(n_jobs=n_cpus_max)  # init model
    model.load_model("../../data/{0}/{0}.linkmodel.json".format(lang))  # load data

    ## load the test-set
    test_set = []
    with open("../../data/{0}/testing/sentences_test.csv".format(lang)) as fin:
        for line in fin:
            try:
                title, sent = line.split("\t")
                test_set.append((title, sent))
            except:
                continue

    if threshold == None:
        list_threshold = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    else:
        list_threshold = [threshold]
    list_result = []
    for threshold in list_threshold:
        dict_eval = {}
        print("threshold: ", threshold)
        tot_TP = 0.0
        tot_rel = 0.0
        tot_ret = 0.0
        count_doc = 0
        for page, page_wikicode in test_set:
            try:
                input_code = page_wikicode
                ## get links from original wikitext (resolve redirects, and )
                inp_pairs = getLinks(input_code, redirects=redirects, pageids=pageids)

                ## if no links in main namespace, go to next item
                if len(inp_pairs) == 0:
                    continue

                input_code_nolinks = mwph.parse(page_wikicode).strip_code()
                output_code = process_page(
                    input_code_nolinks,
                    page,
                    anchors,
                    pageids,
                    redirects,
                    word2vec,
                    model,
                    threshold=threshold,
                    pr=False,
                )

                ## get links from predicted wikitext
                out_pairs = getLinks(output_code, redirects=redirects, pageids=pageids)

                TP = dict(set(inp_pairs.items()).intersection(out_pairs.items()))
                tot_TP += len(TP)
                tot_ret += len(out_pairs)
                tot_rel += len(inp_pairs)
                count_doc += 1
                # if count_doc %N_interval == 0:
                #     # print('----------------------')
                #     print('after %s sentences'%count_doc)
                #     micro_precision = tot_TP/tot_ret
                #     micro_recall    = tot_TP/tot_rel
                #     print("micro_precision:\t", micro_precision)
                #     print("micro_recall:\t"   , micro_recall)
            except:
                pass
            if count_doc == N_max:
                break

        micro_precision = tot_TP / tot_ret
        micro_recall = tot_TP / tot_rel
        print("finished: %s sentences" % count_doc)
        print("micro_precision:\t", micro_precision)
        print("micro_recall:\t", micro_recall)
        print("----------------------")
        dict_eval["threshold"] = threshold
        dict_eval["N"] = count_doc
        dict_eval["micro_precision"] = micro_precision
        dict_eval["micro_recall"] = micro_recall
        list_result.append(dict_eval)
    output_path = "../../data/{0}/testing/{0}.backtest.eval".format(lang)
    df = pd.DataFrame.from_dict(list_result).sort_values(by="threshold")
    df.to_csv(output_path + ".csv")


if __name__ == "__main__":
    main()
