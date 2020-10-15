import pickle
import argparse
from utils import process_page
from utils import getLinks
import mwparserfromhell as mwph
import xgboost as xgb
import multiprocessing

'''
backtesting evlauation of trained model on held-out testset
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang","-l",
                        default=None,
                        type = str,
                        required=True,
                        help="language (wiki) for which to get recommendations (e.g. enwiki or en)")

    parser.add_argument("--nmax","-nmax",
                        default=-1,
                        type = int,
                        help="maximum number of sentences to evaluate")

    parser.add_argument("--threshold","-t",
                        default=0.9,
                        type = float,
                        help="threshold value for links to be recommended")

    args = parser.parse_args()
    lang = args.lang.replace('wiki','')
    threshold = args.threshold
    N_max = args.nmax

    ## open dataset-dicts from pickle files
    anchors = pickle.load( open("../data/{0}/{0}.anchors.pkl".format(lang),'rb') ) 
    pageids = pickle.load( open("../data/{0}/{0}.pageids.pkl".format(lang),'rb') ) 
    redirects = pickle.load( open("../data/{0}/{0}.redirects.pkl".format(lang),'rb') ) 
    word2vec = pickle.load( open("../data/{0}/{0}.w2v.filtered.pkl".format(lang),'rb') ) 
    nav2vec = pickle.load( open("../data/{0}/{0}.nav.filtered.pkl".format(lang),'rb') ) 

    ## load trained model
    ## use a fourth of the cpus, at most 8
    n_cpus_max = min([int(multiprocessing.cpu_count()/4),8])
    model = xgb.XGBClassifier(n_jobs=n_cpus_max)  # init model
    model.load_model('../data/{0}/{0}.linkmodel.bin'.format(lang))  # load data

    ## load the test-set
    test_set = []
    with open('../data/{0}/testing/sentences_test.csv'.format(lang)) as fin:
        for line in fin:
            try:
                title, sent = line.split('\t')
                test_set.append((title, sent))
            except:
                continue
    tot_TP = 0.
    tot_rel = 0.
    tot_ret = 0.
    count_doc = 0

    N_interval = 1000

    output_path = '../data/{0}/testing/{0}.backtest.eval'.format(lang)
    with open(output_path,'w') as fout:
        str_write = 'no-sents\tmicro-prec\tmicro-recall\n'
        fout.write(str_write)

        for page, page_wikicode in test_set:
            input_code = page_wikicode
            ## get links from original wikitext (resolve redirects, and )
            inp_pairs = getLinks(input_code, redirects=redirects, pageids=pageids)
            
            ## if no links in main namespace, go to next item
            if len(inp_pairs)==0:
                continue
            

            input_code_nolinks = mwph.parse(page_wikicode).strip_code()
            output_code = process_page(input_code_nolinks, page, anchors, pageids, redirects, word2vec,nav2vec, model, threshold = threshold, pr=False )
           
            ## get links from predicted wikitext
            out_pairs = getLinks(output_code, redirects=redirects, pageids=pageids)

            TP = dict(set(inp_pairs.items()).intersection(out_pairs.items()))
            tot_TP  += len(TP)
            tot_ret += len(out_pairs)
            tot_rel += len(inp_pairs)
            count_doc+=1
            if count_doc %N_interval == 0:
                print('----------------------')
                print('after %s sentences'%count_doc)
                micro_precision = tot_TP/tot_ret
                micro_recall    = tot_TP/tot_rel
                print("micro_precision:\t", micro_precision)
                print("micro_recall:\t"   , micro_recall)
                str_write = '%s\t%s\t%s\n'%(count_doc,micro_precision,micro_recall)
                fout.write(str_write)



            if count_doc == N_max:
                break

        micro_precision = tot_TP/tot_ret
        micro_recall    = tot_TP/tot_rel
        print('----------------------')
        print('finished: %s sentences'%count_doc)
        print("micro_precision:\t",micro_precision)
        print("micro_recall:\t",  micro_recall)
        str_write = '%s\t%s\t%s\n'%(count_doc,micro_precision,micro_recall)
        fout.write(str_write)

if __name__ == "__main__":
    main()