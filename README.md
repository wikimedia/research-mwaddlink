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
python query.py -id de -p Garnet_Carter
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
DB_BACKEND=mysql \
MEDIAWIKI_API_URL=https://my.wiki.url/w/api.php \
FLASK_APP=api \
FLASK_DEBUG=1 \
SWAGGER_UI_ENABLED=1 \
flask run
```

In production, we use `gunicorn` to serve the Flask app, and the MEDIAWIKI_API_URL parameter is omitted, making the app
select the right Wikipedia URL automatically.

The Swagger UI is enabled via `SWAGGER_UI_ENABLED` environment variable, resulting in API docs at
`http://localhost:5000{$SWAGGER_UI_URL_PREFIX}apidocs`. This is enabled for the external traffic release of the
link recommendation service.

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

You can run the pipeline for a given language (change the variable ```WIKI_ID```)

```bash
WIKI_ID=cswiki ./run-pipeline.sh
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
PYSPARK_PYTHON=python3.7 PYSPARK_DRIVER_PYTHON=python3.7 spark2-submit --master yarn --executor-memory 8G --executor-cores 4 --driver-memory 2G  ./scripts/generate_anchor_dictionary_spark.py $WIKI_ID
```


store in:
```bash
./data/<WIKI_ID>/<WIKI_ID>.anchors.pkl
```
- normalising link-titles (e.g. capitalize first letter) and anchors (lowercase the anchor-string) via ```scripts/utils.py```
- for candidate links, we resolve redirects and only keep main-namespace articles

This also adds the two following helper-dictionaries
```bash
./data/<WIKI_ID>/<WIKI_ID>.pageids.pkl
```
- this is a dictionary of all main-namespace and non-redirect articles with the mapping of {page_title:page_id}

```bash
./data/<WIKI_ID>/<WIKI_ID>.redirects.pkl
```
- this is a dictionary of all main-namespace and redirect articles with the mapping {page_title:page_title_rd}, where page_title_rd is the title of the redirected-to article.


Note that the default setup uses the spark-cluster from stat1008 (in order to use the [anaconda-wmf newpyter](https://wikitech.wikimedia.org/wiki/Analytics/Systems/Jupyter#Newpyter]) setup. This is necessary for filtering the anchor-dictionary by link-probability. Alternatively, one can run:
```bash
python ./scripts/generate_anchor_dictionary.py <WIKI_ID>
```


#### Wikipedia2Vec:
This models semantic relationship.
Get it from: https://github.com/wikipedia2vec/wikipedia2vec then run:
```bash
wikipedia2vec train --min-entity-count=0 --dim-size 50 --pool-size 10 "/mnt/data/xmldatadumps/public/"$WIKI_ID"/latest/"$WIKI_ID"-latest-pages-articles.xml.bz2" "./data/"$WIKI_ID"/"$WIKI_ID".w2v.bin"
```

store in
```bash
./data/<WIKI_ID>/<WIKI_ID>.w2v.bin
```

We filter only those vectors from articles in the main-namespace that are not redirects by running
```bash
python filter_dict_w2v.py $WIKI_ID
```
and storing the resulting dictionary as a pickle
```bash
./data/<WIKI_ID>/<WIKI_ID>.w2vfiltered.pkl
```

#### Raw datasets:
There is a backtesting dataset to a) test the accuracy of the model, and b) train the model.
We mainly want to extract fully formed and linked sentences as our ultimate ground truth.

compute with:
```bash
python ./scripts/generate_backtesting_data.py $WIKI_ID
```

Datasets are then stored in:
```bash
./data/<WIKI_ID>/training/sentences_train.csv
./data/<WIKI_ID>/testing/sentences_test.csv

```

#### Feature datasets:
We need dataset with features and training labels (true link, false link)

compute with:
```bash
python ./scripts/generate_training_data.py <WIKI_ID>
```

This is going to generate a file to be stored here:
```bash
./data/<WIKI_ID>/training/link_train.csv
```

#### XGBoost Classification Model:
This is the main prediction model it takes (Page_title, Mention, Candidate Link) and produces a probability of linking.

compute with:
```bash
python ./scripts/generate_addlink_model.py <WIKI_ID>
```
store in:
```bash
./data/<WIKI_ID>/<WIKI_ID>.linkmodel.json
```

#### Backtesting evaluation:
Evaluate the prediction algorithm on a set of sentences in the training set using micro-precision and micro-recall.

compute with (first 10000 sentences):
```bash
python generate_backtesting_eval.py -l $WIKI_ID -nmax 10000
```
store in:
```bash
./data/<WIKI_ID>/<WIKI_ID>.backtest.eval
```

#### memory-mapping
The pickle-dictionaries (anchors, pageids, redirects, w2v) are converted to sqlite-databases using the [sqlitedict-package](https://pypi.org/project/sqlitedict/) in order to reduce memory-footprint when reading these dictionaries when getting link-recommendations for individual articles.

computed via
```bash
python ./scripts/generate_sqlite_data.py $WIKI_ID
```

stored in
```bash
./data/<WIKI_ID>/<WIKI_ID>.anchors.sqlite
./data/<WIKI_ID>/<WIKI_ID>.pageids.sqlite
./data/<WIKI_ID>/<WIKI_ID>.redirects.sqlite
./data/<WIKI_ID>/<WIKI_ID>.w2vfiltered.sqlite
```

#### Development

Run lint checks with `flake8`: `.venv_query/bin/flake8` or `tox`.

Format your code with [`black`](https://pypi.org/project/black/).

##### Docker Compose

There is a Docker Compose configuration for running the service locally. Run `docker-compose up -d` then use `docker-compose exec linkrecommendation [cmd]` to execute code in the application container.

Note that on macOS hosts there is currently an issue with XGBoost when loading the JSON model:

```
xgboost.core.XGBoostError: [09:00:14] ../src/common/json.cc:449: Unknown construct, around character position: 71
```

See [T275358](https://phabricator.wikimedia.org/T275358) for more information.
