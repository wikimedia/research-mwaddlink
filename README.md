# research/mwaddlink

This is the repository that backs the [Wikimedia Link Recommendation service](https://wikitech.wikimedia.org/wiki/Add_Link). 
It contains code for training a model and generating datasets, as well as an HTTP API and command line interface for 
fetching link recommendations for Wikipedia articles.

The method is context-free and can be scaled to (virtually) any language, provided that we have enough existing links 
to learn from.

## Querying the model

Once the model and all the utility files are computed (see "Training the model" below), they can be loaded and used to 
build an API to add new links to a Wikipedia page automatically.

For this we have the following utilities

* command-line tool:

```bash
python cli.py -id de -p Garnet_Carter
```
This will return all recommended links for a given page (-p) in a given wiki ID (-id). You can also specify the 
threshold for the probability of the link (-t, default=0.9)

* interactive notebook:
```bash
addlink-query_notebook.ipynb
```
This allows you to inspect the recommendations in a notebook.

* HTTP API
``` bash
DB_USER=root \
DB_PASSWORD=password \
DB_PORT=3306 \
DB_HOST=127.0.0.1 \
DB_DATABASE=addlink \
FLASK_DEBUG=1 \
DB_BACKEND=mysql \
FLASK_APP=api \
flask run
```

In production we use `gunicorn` to serve the Flask app.

### Database backends

You can use MySQL (preferred) or SQLite for querying. Set `DB_BACKEND` to `mysql` or `sqlite` for Flask, and for the 
command line scripts there is a flag you can use (`--database-backend`) for specifying which backend to use.

Note that for the CLI, you will still need to pass in the `DB_*` variables referenced above.

### Notes

- You need set up a python virtual environment:

```bash
virtualenv -p /usr/bin/python3 venv_query/
source venv_query/bin/activate
pip install -r requirements-query.txt
```

This contains only the packages required for querying the model and is thus lighter than the environment for training the model.

- on the stat-machines, make sure you have the http-proxy set up https://wikitech.wikimedia.org/wiki/HTTP_proxy
- you might have to install the following nltk-package manually: ```python -m nltk.downloader punkt```

## Training the model

To load, the API will need to pre-compute the some datasets for each target language.

It is essential to follow these steps sequentially because some scripts may require the output of previous ones.

You can run the pipeline for a given language (change the variable ```LANG```)

```bash
./run-pipeline.sh
```

**Notes**:
- we need set up a python virtual environment:
```bash
virtualenv -p /usr/bin/python3 venv/
source venv/bin/activate
pip install -r requirements.txt
```

- some parts in the script rely on using the spark cluster using a specific conda-environment from a specific stat-machine (stat1008).
- on the stat-machines, make sure you have the http-proxy set up https://wikitech.wikimedia.org/wiki/HTTP_proxy
- you might have to install the following nltk-package manually: ```python -m nltk.downloader punkt```

#### Anchors Dictionary
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


#### Wikipedia2Vec:
This models semantic relationship.
Get it from: https://github.com/wikipedia2vec/wikipedia2vec then run:
```bash
wikipedia2vec train --min-entity-count=0 --dim-size 50 --pool-size 10 "/mnt/data/xmldatadumps/public/"$LANG"wiki/latest/"$LANG"wiki-latest-pages-articles.xml.bz2" "./data/"$LANG"/"$LANG".w2v.bin"
```

store in
```bash
./data/<LANG>/<LANG>.w2v.bin
```

We filter only those vectors from articles in the main-namespace that are not redirects by running
```bash
python filter_dict_w2v.py $LANG
```
and storing the resulting dictionary as a pickle
```bash
./data/<LANG>/<LANG>.w2vfiltered.pkl
```


#### Nav2Vec:
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

We filter only those vectors from articles in the main-namespace that are not redirects by running
```bash
python filter_dict_nav.py $LANG
```
and storing the resulting dictionary as a pickle
```bash
./data/<LANG>/<LANG>.navfiltered.pkl
```

#### Raw datasets:
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

#### Feature datasets:
We need dataset with features and training labels (true link, false link)

compute with:
```bash
python ./scripts/generate_training_data.py <LANG>
```

This is going to generate a file to be stored here:
```bash
./data/<LANG>/training/link_train.csv
```

#### XGBoost Classification Model:
This is the main prediction model it takes (Page_title, Mention, Candidate Link) and produces a probability of linking.

compute with:
```bash
python ./scripts/generate_addlink_model.py <LANG>
```
store in:
```bash
./data/<LANG>/<LANG>.linkmodel.json
```

#### Backtesting evaluation:
Evaluate the prediction algorithm on a set of sentences in the training set using micro-precision and micro-recall.

compute with (first 10000 sentences):
```bash
python generate_backtesting_eval.py -l $LANG -nmax 10000
```
store in:
```bash
./data/<LANG>/<LANG>.backtest.eval
```

#### memory-mapping
The pickle-dictionaries (anchors, pageids, redirects, w2v,nav) are converted to sqlite-databases using the [sqlitedict-package](https://pypi.org/project/sqlitedict/) in order to reduce memory-footprint when reading these dictionaries when getting link-recommendations for individual articles.

computed via
```bash
python ./scripts/generate_sqlite_data.py $LANG
```

stored in
```bash
./data/<LANG>/<LANG>.anchors.sqlite
./data/<LANG>/<LANG>.pageids.sqlite
./data/<LANG>/<LANG>.redirects.sqlite
./data/<LANG>/<LANG>.w2vfiltered.sqlite
./data/<LANG>/<LANG>.navfiltered.sqlite
```

#### Development

Run lint checks with `flake8`: `.venv_query/bin/flake8` or `tox`.

Formt your code with [`black`](https://pypi.org/project/black/).
