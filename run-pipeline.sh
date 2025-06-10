#!/bin/bash
set -ex

# on stat-machine you might have to "kinit" first

WIKI_ID=${WIKI_ID:-simplewiki}
DATASET_PATH=$(pwd)/data/${WIKI_ID}

cd src/scripts/

echo "CREATING FOLDERS for data in ${DATASET_PATH}"
mkdir -p "$DATASET_PATH/training"
mkdir -p "$DATASET_PATH/testing"

echo 'GETTING THE ANCHOR DICTIONARY'
# activate conda env (python3.10) to run spark jobs
source conda-analytics-activate link-recommendation-env
conda list
if [ ! -f environment.tar.gz ]; then
  conda pack -o environment.tar.gz
fi
PYSPARK_PYTHON=~/.conda/envs/link-recommendation-env/bin/python3.10 PYSPARK_DRIVER_PYTHON=~/.conda/envs/link-recommendation-env/bin/python3.10 spark3-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G --conf spark.dynamicAllocation.maxExecutors=128 --archives environment.tar.gz#environment generate_anchor_dictionary_spark.py $WIKI_ID
# get wikidata-properties to filter, e.g., disambiguation pages as links
PYSPARK_PYTHON=~/.conda/envs/link-recommendation-env/bin/python3.10 PYSPARK_DRIVER_PYTHON=~/.conda/envs/link-recommendation-env/bin/python3.10 spark3-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  --conf spark.dynamicAllocation.maxExecutors=128 --archives environment.tar.gz#environment generate_wdproperties_spark.py $WIKI_ID
python filter_dict_anchor.py $WIKI_ID

# alternatively, one can get the anchor-dictionary by processing the xml-dumps
# note that this does not filter by link-probability
# python generate_anchor_dictionary.py $WIKI_ID

# deactivate conda env
conda deactivate

# activate python3.7 env to:
#   - train wikipedia2vec and filter its output
#   - run sqlitedict which sets pickle protocol using HIGHEST_PROTOCOL
#     the goal is to have sqlitedict use protocol 4 instead of 5
source ../../venv/bin/activate

echo 'RUNNING wikipedia2vec on dump'
ionice wikipedia2vec train \
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
DB_HOST=${DB_HOST:-staging-db-analytics.eqiad.wmnet}
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

# deactivate python3.7 env
deactivate

# Remove the old linkmodel.json file from /tmp, in case we are testing
# out queries on stat1008.
rm /tmp/"$WIKI_ID".linkmodel.json || true
