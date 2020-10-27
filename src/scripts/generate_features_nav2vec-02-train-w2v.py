import os, sys
import datetime
import calendar
import time
import string
import random
import argparse

import fasttext

'''
training w2v-model on reading sessions
- saves the model in ../data/<LANG>/<LANG>.nav.bin

USAGE: python generate_features_nav2vec-02-train-w2v.py -l simple

requires to run generate_features_nav2vec-01-get-sessions.py for a given wiki
'''

## TODO: define output filenames and intermediate filenames and paths

def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument("--file_input","-fin",
    #                     default=None,
    #                     type = str,
    #                     help="path to file with input corpus")

    # parser.add_argument("--file_output","-fout",
    #                     default='tmp.nav2vec-model.bin',
    #                     type = str,
    #                     help="path to save trained w2v-model")

    parser.add_argument("--lang","-l",
                        default=None,
                        type = str,
                        required=True,
                        help="language to parse train model")

    parser.add_argument("--mode","-m",
                        default='cbow',
                        type = str,
                        help="w2v option: mode cbow or skipgram")
    parser.add_argument("--size","-s",
                        default=50,
                        type = int,
                        help="w2v option: number of dimensions (size of vector")
    parser.add_argument("--window","-ws",
                        default=5,
                        type = int,
                        help="w2v option: size of context window")    
    parser.add_argument("--sample","-t",
                        default=0.0001,
                        type = float,
                        help="w2v option: sampling threshold")   
    parser.add_argument("--negative","-n",
                        default=10,
                        type = int,
                        help="w2v option: number of negative samples")  
    parser.add_argument("--min_count","-min",
                        default=1,
                        type = int,
                        help="w2v option: minimum number of times a word has to appear in the corpus")  
    parser.add_argument("--epochs","-e",
                        default=10,
                        type = int,
                        help="w2v option: number of iterations")  
    parser.add_argument("--workers","-w",
                        default=10,
                        type = int,
                        help="how many cpus to use")  
    parser.add_argument("--remove_fin","-rfin",
                        default=False,
                        type = bool,
                        help="put yes if you want to remove the reading sessions-file (default:False")  


    args = parser.parse_args()

    # FILE_in = args.file_input
    # FILE_out = args.file_output
    # if FILE_in == None:
    #     print('specify path to data')

    ##
    lang = args.lang.replace('wiki','')
    wiki_db = lang+'wiki'

    ## sessions will be saved locally in filename_save
    PATH_data = os.path.abspath('../data/%s/'%lang)
    FILE_in = os.path.join(PATH_data,'%s.reading-sessions'%(lang))
    FILE_out = os.path.join(PATH_data,'%s.nav.bin'%(lang))

    mode = args.mode ## (if 1: skip-gram, else cbow)
    size = args.size ## number of dimensions
    window = args.window ## context window size
    sample = args.sample ## downsample high-frequency words
    negative = args.negative ##negative sampling (noise words)
    min_count = args.min_count ## words with less occurrences in total will be ignored
    epochs  = args.epochs ## number of iterations
    workers = args.workers ## number of cores to use

    ##training the model
    model = fasttext.train_unsupervised(FILE_in, \
        dim = size, epoch=epochs, model=mode,minCount=min_count,ws=window,neg=negative, t=sample,\
        thread=workers,
        maxn=0)
    ## save model
    model.save_model(FILE_out)

    ## remove reading session file
    if args.remove_fin == True:
        os.system('rm -r %s'%FILE_in)

if __name__ == "__main__":
    main()