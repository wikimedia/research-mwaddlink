# mwaddlink
MediaWiki AddLink Extension Model and API

## Introduction
This repository contains the necessary code to train a model for link recommendation tailored for Wikipedia.
The method is context-free and can be scaled to (virtually) any language, provided that we have enough existing links to learn from.
Once the model and all the utility files are computed, they can be loaded and used to build an API to add new links to a Wikipedia page automatically. The necessary code for such an API is available in the following notebook:

```bash
link_page_simple.ipynb
```

The primary function will take a Wikipedia page_title, queries the API for its wikitext, and returns new wikitext.
TODO: make it return an object containing information about the number of links added (if at all) and the confidence of the model on each link.

## Data preparation

To load, the API will need to pre-compute the some datasets for each target language.

It is essential to follow these steps sequentially because some scripts may require the output of previous ones.

You can run the pipeline for a given language (change the variable ```LANG```)

```bash
./run-pipeline.sh
```

Note1: we need set up a python virtual environment:
```bash
virtualenv -p /usr/bin/python3 venv/
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

Note2: some parts in the script rely on using the spark cluster using a specific conda-environment from a specific stat-machine (stat1008).

Specifically, the script is creating the following datasets.

### Anchors Dictionary
This is the main dictionary to find candidates and mentions; the bigger, the better (barring memory issues) for English, this is a ~2G pickle file.

compute with:
```bash
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  ./scripts/generate_anchor_dictionary_spark.py $LANG
```


store in:
```bash
./data/<LANG>/<LANG>.anchors.pkl
```
- normalising link-titles (e.g. capitalize first letter) and anchors (lowercase the anchor-string) via ```scripts/utils.py```
- for candidate links, we resolve redirects and only keep main-namespace articles

This also adds the two following helper-dictionaries
```bash
./data/<LANG>/<LANG>.pageids.pkl
```
- this is a dictionary of all main-namespace and non-redirect articles with the mapping of {page_title:page_id}

```bash
./data/<LANG>/<LANG>.redirects.pkl
```
- this is a dictionary of all main-namespace and redirect articles with the mapping {page_title:page_title_rd}, where page_title_rd is the title of the redirected-to article.


Note that the default setup uses the spark-cluster from stat1008 (in order to use the [anaconda-wmf newpyter](https://wikitech.wikimedia.org/wiki/Analytics/Systems/Jupyter#Newpyter]) setup. This is necessary for filtering the anchor-dictionary by link-probability. Alternatively, one can run:
```bash
python ./scripts/generate_anchor_dictionary.py <LANG>
```


### Wikipedia2Vec:
This models semantic relationship.
Get it from: https://github.com/wikipedia2vec/wikipedia2vec then run:
```bash
wikipedia2vec train --min-entity-count=0 --dim-size 50 --pool-size 10 "/mnt/data/xmldatadumps/public/"$LANG"wiki/latest/"$LANG"wiki-latest-pages-articles.xml.bz2" "./data/"$LANG"/"$LANG".w2v.bin"
```

store in
```bash
./data/<LANG>/<LANG>.w2v.bin
```

### Nav2Vec:
This models how current Wikipedia readers navigate through Wikipedia.

compute via:
```bash
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  ./scripts/generate_features_nav2vec-01-get-sessions.py -l $LANG
```
- gets reading sessions from webrequest from 1 week (this can be changed)

```bash
python ./scripts/generate_features_nav2vec-02-train-w2v.py -l $LANG -rfin True
```
- fits a word2vec-model with 50 dimensions (this and other hyperparameters can also be changed)

This will generate an embedding for <LANG> in
```bash
./data/<LANG>/<LANG>.nav.bin
```

### Filtering and memory-mapping
The pickle-dictionaries (anchors, pageids, redirects) are converted to sqlite-databases using the [sqlitedict-package](https://pypi.org/project/sqlitedict/) in order to reduce memory-footprint when reading these dictionaries later.

computed via
```bash
python ./scripts/generate_sqlite_data.py $LANG
```

stored in
```bash
./data/<LANG>/<LANG>.anchors.sqlite
./data/<LANG>/<LANG>.pageids.sqlite
./data/<LANG>/<LANG>.redirects.sqlite
```

Similarly, we store the embeddings from wikiepdia2vec and nav2vec into sqlite-databases; at the same time we are filtering to keep only pages from main-namespace that are not redirects to reduce the size of these files.

stored in
```bash
./data/<LANG>/<LANG>.w2v.filtered.sqlite
./data/<LANG>/<LANG>.nav.filtered.sqlite
```


### Raw datasets:
There is a backtesting dataset to a) test the accuracy of the model, and b) train the model.
We mainly want to extract fully formed and linked sentences as our ultimate ground truth.

compute with:
```bash
python ./scripts/generate_backtesting_data.py $LANG
```

Datasets are then stored in:
```bash
./data/<LANG>/training/sentences_train.csv
./data/<LANG>/testing/sentences_test.csv

```

### Feature datasets:
We need dataset with features and training labels (true link, false link)

compute with:
```bash
python ./scripts/generate_training_data.py <LANG>
```

This is going to generate a file to be stored here:
```bash
./data/<LANG>/training/link_train.csv
```

### XGBoost Classification Model:
This is the main prediction model it takes (Page_title, Mention, Candidate Link) and produces a probability of linking.

compute with:
```bash
python ./scripts/generate_addlink_model.py <LANG>
```
store in:
```bash
./data/<LANG>/<LANG>.linkmodel.bin
```

### Backtesting evaluation:
Evaluate the prediction algorithm on a set of sentences in the training set using micro-precision and micro-recall.

compute with (first 10000 sentences):
```bash
python generate_backtesting_eval.py -l $LANG -nmax 10000
```
store in:
```bash
./data/<LANG>/<LANG>.backtest.eval
```
