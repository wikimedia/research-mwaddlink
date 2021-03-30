#!/bin/bash
set -e

# on stat-machine you might have to "kinit" first

WIKI_ID=${WIKI_ID:-simplewiki}
DATASET_PATH=$(pwd)/data/${WIKI_ID}

cd src/scripts/

echo "CREATING FOLDERS for data in ${DATASET_PATH}"
mkdir -p "$DATASET_PATH/training"
mkdir -p "$DATASET_PATH/testing"

echo 'GETTING THE ANCHOR DICTIONARY'
# for the anchor dictionary we use the conda-environment on stats
source /usr/lib/anaconda-wmf/bin/activate
PYSPARK_PYTHON=/usr/lib/anaconda-wmf/bin/python3.7 PYSPARK_DRIVER_PYTHON=/usr/lib/anaconda-wmf/bin/python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_anchor_dictionary_spark.py $WIKI_ID
# get wikidata-properties to filter, e.g., disambiguation pages as links
PYSPARK_PYTHON=/usr/lib/anaconda-wmf/bin/python3.7 PYSPARK_DRIVER_PYTHON=/usr/lib/anaconda-wmf/bin/python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_wdproperties_spark.py $WIKI_ID
python filter_dict_anchor.py $WIKI_ID
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

echo 'RUNNING wikipedia2vec on dump'
wikipedia2vec train \
  --min-entity-count=0 \
  --dim-size 50 \
  --pool-size 8 \
  "/mnt/data/xmldatadumps/public/${WIKI_ID}/latest/${WIKI_ID}-latest-pages-articles.xml.bz2" \
  "../../data/${WIKI_ID}/${WIKI_ID}.w2v.bin"

python filter_dict_w2v.py $WIKI_ID

echo 'GENERATING BACKTESTING DATA'
python generate_backtesting_data.py $WIKI_ID

echo 'GENERATING FEATURES'
python generate_training_data.py $WIKI_ID

echo 'TRAINING THE MODEL'
python generate_addlink_model.py $WIKI_ID

echo 'RUNNING BACKTESTING EVALUATION'
python generate_backtesting_eval.py -id $WIKI_ID -nmax 10000

echo 'CONVERTING DATA TO SQLITE FORMAT'
python generate_sqlite_data.py $WIKI_ID

echo 'MOVING SQLITE DATA TO MYSQL-DATABASE (STAGING)'
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
python create_tables.py -id "$WIKI_ID"

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

if [ $VENV_ACTIVATED -ne 0 ]; then
  deactivate
fi

# Remove the old linkmodel.json file from /tmp, in case we are testing
# out queries on stat1008.
rm /tmp/"$WIKI_ID".linkmodel.json || true
