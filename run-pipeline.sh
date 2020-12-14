#!/bin/bash

set -ex

# on stat-machine you might have to "kinit" first

WIKI_ID=${WIKI_ID:-simple}

## go to scripts directory
cd src/scripts/

# # create folder for data
echo "CREATING FOLDERS for data in ../data/${WIKI_ID}"

mkdir ../../data/$WIKI_ID
mkdir ../../data/$WIKI_ID/training
mkdir ../../data/$WIKI_ID/testing


echo 'GETTING THE ANCHOR DICTIONARY'
deactivate
source ../../venv/bin/activate
deactivate


source /usr/lib/anaconda-wmf/bin/activate
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_anchor_dictionary_spark.py $WIKI_ID
conda deactivate

source ../../venv/bin/activate
# alternatively, one can get the anchor-dictionary by processing the xml-dumps
# note that this does not filter by link-probability
# python generate_anchor_dictionary.py $WIKI_ID


## get wikipedia2vec-mebddingq
echo 'RUNNING wikipedia2vec on dump'
wikipedia2vec train \
  --min-entity-count=0 \
  --dim-size 50 \
  --pool-size 10 \
  "/mnt/data/xmldatadumps/public/${WIKI_ID}/latest/${WIKI_ID}-latest-pages-articles.xml.bz2" \
  "../../data/${WIKI_ID}/${WIKI_ID}.w2v.bin"

python filter_dict_w2v.py $WIKI_ID

# # generate backtesting data
echo 'GENERATING BACKTESTIN DATA'
python generate_backtesting_data.py $WIKI_ID

# # turn into features
echo 'GENERATING FEATURES'
python generate_training_data.py $WIKI_ID

#  train model
echo 'TRAINING THE MODEL'
python generate_addlink_model.py $WIKI_ID

# ## perform automatic backtesting
echo 'RUNNING BACKTESTING EVALUATION'
python generate_backtesting_eval.py -l $WIKI_ID -nmax 100000 -t 0.5

# # converting data to sqlite format
echo 'CONVERTING DATA TO SQLITE FORMAT'
python generate_sqlite_data.py $WIKI_ID

echo 'MOVING SQLITE DATA TO MYSQL-DATABASE (STAGING)'
# config needed to access database (might be subject to change depending from where this is run)
cd ../../

 DB_USER=research \
 DB_DATABASE=staging \
 DB_HOST=dbstore1005.eqiad.wmnet \
 DB_PORT=3350 \
 DB_READ_DEFAULT_FILE=/etc/mysql/conf.d/analytics-research-client.cnf python create-tables.py -id $WIKI_ID

 DB_USER=research \
 DB_DATABASE=staging \
 DB_HOST=dbstore1005.eqiad.wmnet \
 DB_PORT=3350 \
 DB_READ_DEFAULT_FILE=/etc/mysql/conf.d/analytics-research-client.cnf python copy-sqlite-to-mysql.py -id $WIKI_ID