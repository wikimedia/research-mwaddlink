#!/bin/bash

set -ex

# on stat-machine you might have to "kinit" first

WIKI_ID=${WIKI_ID:-simplewiki}
DATASET_PATH=$(pwd)/data/${WIKI_ID}

## go to scripts directory
cd src/scripts/

# # create folder for data
echo "CREATING FOLDERS for data in ${DATASET_PATH}"

mkdir "$DATASET_PATH"
mkdir "$DATASET_PATH/training"
mkdir "$DATASET_PATH/testing"

echo 'GETTING THE ANCHOR DICTIONARY'
# for the anchor dictionary we use the conda-environment on stats
source /usr/lib/anaconda-wmf/bin/activate
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_anchor_dictionary_spark.py $WIKI_ID
conda deactivate

# activate the custom virtual environment, unless it's already active
VENV_ACTIVATED=0
if [ -z "$VIRTUAL_ENV" ]; then
  VENV_ACTIVATED=1
  source ../../venv/bin/activate
fi
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
python generate_backtesting_eval.py -id $WIKI_ID -nmax 10000

# # converting data to sqlite format
echo 'CONVERTING DATA TO SQLITE FORMAT'
python generate_sqlite_data.py $WIKI_ID

echo 'MOVING SQLITE DATA TO MYSQL-DATABASE (STAGING)'
# config needed to access database (might be subject to change depending from where this is run)
cd ../../

DB_USER=${DB_USER:-research}
DB_DATABASE=${DB_DATABASE:-staging}
DB_HOST=${DB_HOST:-dbstore1005.eqiad.wmnet}
DB_PORT=${DB_PORT:-3350}
DB_READ_DEFAULT_FILE=${DB_READ_DEFAULT_FILE:-/etc/mysql/conf.d/analytics-research-client.cnf}

DB_USER=$DB_USER \
DB_DATABASE=$DB_DATABASE \
DB_HOST=$DB_HOST \
DB_PORT=$DB_PORT \
DB_READ_DEFAULT_FILE=$DB_READ_DEFAULT_FILE \
python create-tables.py -id "$WIKI_ID"

DB_USER=$DB_USER \
DB_DATABASE=$DB_DATABASE \
DB_HOST=$DB_HOST \
DB_PORT=$DB_PORT \
DB_READ_DEFAULT_FILE=$DB_READ_DEFAULT_FILE \
python copy-sqlite-to-mysql.py -id "$WIKI_ID"

DB_USER=$DB_USER \
DB_DATABASE=$DB_DATABASE \
DB_HOST=$DB_HOST \
DB_PORT=$DB_PORT \
DB_READ_DEFAULT_FILE=$DB_READ_DEFAULT_FILE \
python export-tables.py -id "$WIKI_ID" --path "$DATASET_PATH"

echo "Generated datasets in $DATASET_PATH"
echo "To publish the datasets, run \"WIKI_ID=$WIKI_ID ./publish-datasets.sh\""

# deactivate the virtual environment
if [ $VENV_ACTIVATED -ne 0 ]; then
  deactivate
fi

# Remove the old linkmodel.json file from /tmp, in case we are testing
# out queries on stat1008.
rm /tmp/"$WIKI_ID".linkmodel.json || true
