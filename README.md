# mwaddlink
MediaWiki AddLink Extension Model and API

## Introduction
This repository contains the necessary code to train a model for link recommendation tailored for Wikipedia.
The method is context-free and can be scaled to (virtually) any language, provided that we have enough existing links to learn from.
Once the model and all the utility files are computed, they can be loaded and used to build an API to add new links to a Wikipedia page automatically. The necessary code for such an API is available in the following notebook:

```bash
link_page_english.ipynb
```

The primary function will take a Wikipedia page_title, queries the API for its wikitext, and returns new wikitext.
TODO: make it return an object containing information about the number of links added (if at all) and the confidence of the model on each link.

## Data preparation

To load, the API will need to pre-compute the following files for each target language. For now, the scripts support English (en).

It is essential to follow these steps sequentially because some scripts may require the output of previous ones.

### Nav2Vec:
This models how current Wikipedia readers navigate through Wikipedia.

run the two scripts in that order for a given <LANG> (e.g. 'en'), located in ```./scripts```:
```bash
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  generate_features_nav2vec-01-get-sessions.py -l <LANG>
```
- gets reading sessions from webrequest from 1 week (this can be changed)

```bash
python generate_features_nav2vec-02-train-w2v.py -l <LANG>
```
- fits a word2vec-model with 50 dimensions (this and other hyperparameters can also be changed)

This will generate an embedding for <LANG> in 
```bash
./data/<LANG>/<LANG>.nav.bin
```

(The previous version was stored in:)
```bash
./data/en/word2vec_enwiki_params-cbow-50-5-0.1-10-5-20.bin
```

### Wikipedia2Vec:
This models semantic relationship.
Get it from: https://github.com/wikipedia2vec/wikipedia2vec then run:
```bash
wikipedia2vec train --min-entity-count=0 --dim-size 100 enwiki-latest-pages-articles.xml.bz2 en.w2v.bin
```

store in
```bash
./data/en/en.w2v.bin
```

### Anchors Dictionary
This is the main dictionary to find candidates and mentions; the bigger, the better (barring memory issues) for English, this is a ~2G pickle file.

compute with: ./scripts/generate_anchor_dictionary.py <LANG>

store in:
```bash
./data/en/en.anchors.pkl
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


All dictionaries are also stored as shelve-format (.db instead of .pkl).


### Raw datasets:
There is a backtesting dataset to a) test the accuracy of the model, and b) train the model.
We mainly want to extract fully formed and linked sentences as our ultimate ground truth.

compute with: ./scripts/generate_backtesting_data.py

Datasets are then stored in:
```bash
./data/en/training/sentences_test.csv
./data/en/training/sentences_train.csv
```

### Feature datasets:
We need dataset with features and training labels (true link, false link)

compute with: ./scripts/generate_training_data.py <LANG>

This is going to generate a file to be stored here:
```bash
./data/<LANG>/training/link_train.csv
```

### XGBoost Classification Model:
This is the main prediction model it takes (Page_title, Mention, Candidate Link) and produces a probability of linking.

compute with: ./scripts/generate_addlink_model.py <LANG>

store in:
```bash
./data/<LANG>/0001.link.bin
```
