#!/bin/bash
## note that some files still have an extension _simple
## this refers to scripts not yet adapted

# activate the venv
# go to scripts folder
# cd scripts/


# # WIKI=simple
## TODO add lang as parameter
LANG=de

## go to scripts directory
cd scripts/

# # create folder for data
echo 'CREATING FOLDERS for data in ../data/'$LANG
mkdir ../data/$LANG
mkdir ../data/$LANG/training

echo 'GETTING THE ANCHOR DICTIONARY'
deactivate
source /usr/lib/anaconda-wmf/bin/activate
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_anchor_dictionary_spark.py $LANG
conda deactivate

# alternatively, one can get the anchor-dictionary by processing the xml-dumps
# note that this does not filter by link-probability
# source ~/venv_custom/mwaddlink/bin/activate
# python generate_anchor_dictionary.py $LANG

source ~/venv_custom/mwaddlink/bin/activate

get wikipedia2vec-mebddingq
echo 'RUNNING wikipedia2vec on dump'
wikipedia2vec train --min-entity-count=0 --dim-size 50 --pool-size 10 "/mnt/data/xmldatadumps/public/"$LANG"wiki/latest/"$LANG"wiki-latest-pages-articles.xml.bz2" "../data/"$LANG"/"$LANG".w2v.bin"

# get navigation features (remove the reading sessions and only keep the model)
# echo 'RUNNING nav2vec'
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_features_nav2vec-01-get-sessions.py -l $LANG
python generate_features_nav2vec-02-train-w2v.py -l $LANG -rfin True

# # generate backtesting data
echo 'GENERATING BACKTESTIN DATA'
python generate_backtesting_data.py $LANG

# # converting data to shelve format
echo 'CONVERTING DATA TO SHELVE FORMAT'
python generate_shelve_data.py $LANG

# # turn into features
echo 'GENERATING FEATURES'
python generate_training_data.py $LANG

#  train model
echo 'TRAINING THE MODEL'
python generate_addlink_model.py $LANG

# ## perform automatic backtesting
echo 'RUNNING BACKTESTING EVALUATION'
python generate_backtesting_eval.py -l $LANG -nmax 10000