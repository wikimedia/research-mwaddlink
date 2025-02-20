# research/mwaddlink

This is the repository that backs the [Wikimedia Link Recommendation service](https://wikitech.wikimedia.org/wiki/Add_Link).

It contains code for training a model and generating datasets, as well as an HTTP API and command line interface for
fetching link recommendations for Wikipedia articles.

The method is context-free and can be scaled to (virtually) any language, provided that we have enough existing links
to learn from.

## Setting up the virtual environment

We need to set up two python virtual environments to have all necessary packages:

#### 1. python3.10 conda env to run spark jobs
```
$ conda-analytics-clone link-recommendation-env
$ source conda-analytics-activate link-recommendation-env
$ export http_proxy=http://webproxy.eqiad.wmnet:8080
$ export https_proxy=http://webproxy.eqiad.wmnet:8080
$ pip install $(grep -ivE "wikipedia2vec" requirements.txt)
```

#### 2. python3.9 env to run `wikipedia2vec` and `sqlitedict`
```
# assumes you are still working from the directory that you downloaded from the project repo
$ virtualenv -p python3.9 venv
$ source venv/bin/activate
$ pip install $(grep -ivE "wmfdata" requirements.txt)
```

There are a few caveats:
- Make sure you have kerberos credentials enabled on the stat-machines by typing “kinit” (see the [User guide](https://wikitech.wikimedia.org/wiki/Analytics/Systems/Kerberos/UserGuide) for more details). Otherwise running the pipeline and training the model will fail when executing the spark-jobs.
- some parts in the script rely on using the spark cluster using a specific conda-environment from a specific stat-machine (stat1008).
- on the stat-machines, make sure you have the http-proxy set up https://wikitech.wikimedia.org/wiki/HTTP_proxy
- you might have to install the following nltk-package manually: ```python -m nltk.downloader punkt```
- in case of [wikipedia2vec](https://github.com/wikipedia2vec/wikipedia2vec) installation issues, refer to: https://wikipedia2vec.github.io/wikipedia2vec/install/
- [PyICU](https://gitlab.pyicu.org/main/pyicu) has its own installation process; see [#installing-pyicu](https://gitlab.pyicu.org/main/pyicu#installing-pyicu) for up-to-date instructions.

## Training the model

The full pipeline to train the model and generate the underlying datasets for a Wikipedia can be run by the following command.
```
WIKI_ID=<WIKI_ID> ./run-pipeline.sh
```
For example, for the Czech Wikipedia use \<WIKI_ID\>=cswiki

This pipeline exectues the following scripts

#### Creating the directories in data/
The first step generates the following directories
- ```./data/<WIKI_ID>```
- ```./data/<WIKI_ID>/training```
- ```./data/<WIKI_ID>/testing```

#### src/script/generate_anchor_dictionary_spark.py
Spark-job that generates the anchor dictionary (\*.anchors.pkl) and helper-dictionaries for lookup (\*.pageids.pkl, \*.redirects.pkl) from dumps. This generates the following files:
- ```./data/<WIKI_ID>/<WIKI_ID>.anchors.pkl``` Format: {mention: [candidate_link_title:number_of_occurrences,] }
- ```./data/<WIKI_ID>/<WIKI_ID>.pageids.pkl``` Format: {page_id:page_title}
- ```./data/<WIKI_ID>/<WIKI_ID>.redirects.pkl``` Format: {redirect_from_title:redirect_to_title}

#### src/script/generate_wdproperties_spark.py
Spark-job that generates the wikidata-property dictionary (\*.wdproperties.pkl). For each pageid, it stores the Wikidata-items listed as values for a pre-defined set of properties (e.g. P31). This generates the following files:
- ```./data/<WIKI_ID>/<WIKI_ID>.wdproperties.pkl``` Format: {page_id:[wikidata_item,]}

#### src/script/filter_dict_anchor.py
Filters all pages from the anchor-dictionary that have a Wikidata-property from a pre-defined set (e.g. instance_of=date). The filter is defined manually at the beginning of the script. This generates the following files:
- ```./data/<WIKI_ID>/<WIKI_ID>.anchors.pkl``` Note:this file already exists before and is only filtered so that some items are removed

#### src/script/wikipedia2vec train
Runs the [wikipedia2vec algorithm](https://wikipedia2vec.github.io/wikipedia2vec/commands/) from the wikipedia2vec-package on an XML-dump of Wikipedia using several cores. This generates an embedding for each article in several in several intermediate files. This generates the following files (among others):
- ```./data/<WIKI_ID>/<WIKI_ID>.w2v.bin``` Note: All of them are only intermediate datasets and will be deleted in the next step.

#### src/script/filter_dict_w2v.py
Filters the files associated to the article-embeddings generated from wikipedia2vec into a single dictionary (\*.w2vfiltered.pkl). This generates the following files:
- ```./data/<WIKI_ID>/<WIKI_ID>.w2vfiltered.pkl```

#### src/script/generate_backtesting_data.py
Extracts a pre-defined number of sentences containing links (from each article only the first sentence that contains at least one link ). The sentences are split into training and testing. This generates the following files:
- ```./data/<WIKI_ID>/training/sentences_train.csv``` Format: page_title \t sentence_wikitext \n
- ```./data/<WIKI_ID>/testing/sentences_test.csv``` Format: page_title \t sentence_wikitext \n

#### src/script/generate_training_data.py
Parse the training sentences and transform into a training set of positive and negative examples of links with features. This generates the following files:
- ```./data/<WIKI_ID>/training/link_train.csv``` Format: page_title \t mention_text \t link_title \t feature_1 \t … \t feature_n \t label

#### src/script/generate_addlink_model.py
Train a classifier-model using [XGBoost](https://xgboost.readthedocs.io) to predict links based on features. This generates the following files:
- ```./data/<WIKI_ID>/<WIKI_ID>.linkmodel.json``` contains parameters of the model, can be loaded via XGBoost.

#### src/script/generate_backtesting_eval.py
Run backtesting evaluation of the link recommendation model on the test sentences. Output is precision and recall metrics for several values of the link-threshold. This generates the following files:
- ```./data/<WIKI_ID>/testing/<WIKI_ID>.backtest.eval.csv``` Format:  index, threshold, number_of_sentences, precision, recall \n

#### src/script/generate_sqlite_data.py
Save the dictionaries in the pkl-files as SQLite-tables using [SqliteDict](https://pypi.org/project/sqlitedict/). Also creates a gzipped version (\*.gz) of each SQLite-file as well as a checksum. This generates the following files:
- ```./data/<WIKI_ID>/<WIKI_ID>.anchors.sqlite```
- ```./data/<WIKI_ID>/<WIKI_ID>.pageids.sqlite```
- ```./data/<WIKI_ID>/<WIKI_ID>.redirects.sqlite```
- ```./data/<WIKI_ID>/<WIKI_ID>.w2vfiltered.sqlite```

Note: for each of the four files there will be two additional files
- ```*.gz``` A gzipped-version of the same SQLite-file
- ```*.checksum``` A checksum generated from the SQLite file

#### create_tables.py
Creates the MySQL-tables in the staging-database on stat1008. Some rudimentary information about the tables are on the wikitech-documentation for [Analytics/Systems/MariaDB](https://wikitech.wikimedia.org/wiki/Analytics/Systems/MariaDB). This setup was suggested in [T265610#6591437](https://phabricator.wikimedia.org/T265610#6591437). This creates the following tables in the staging-databases:
- ```lr_model``` Stores the content from the JSON-file (```./data/<WIKI_ID>/\<WIKI_ID\>.linkmodel.json```). There is one table for all wiki_id. Each wiki_id is a row. Thus the table should exist the first time the pipeline was run for any language.
- ```lr_<WIKI_ID>_anchors``` Stores the content from ```./data/<WIKI_ID>/<WIKI_ID>.anchors.sqlite```
- ```lr_<WIKI_ID>_redirects``` Stores the content from ```./data/<WIKI_ID>/<WIKI_ID>.redirects.sqlite```
- ```lr_<WIKI_ID>_pageids``` Stores the content from ```./data/<WIKI_ID>/<WIKI_ID>.pageids.sqlite```
- ```lr_<WIKI_ID>_w2vfiltered``` Stores the content from ```./data/<WIKI_ID>/<WIKI_ID>.w2vfiltered.sqlite```

#### copy-sqlite-to-mysql.py
Populates the MySQL-tables described above with the content from the SQLite tables.

#### export-tables.py
Creates dump-files of the MySQL tables (\*.sql.gz) as well as checksums (\*.sql.gz.checksum). This generates the following files:
- ```./data/<WIKI_ID>/lr_<WIKI_ID>_anchors.sql.gz```
- ```./data/<WIKI_ID>/lr_<WIKI_ID>_pageids.sql.gz```
- ```./data/<WIKI_ID>/lr_<WIKI_ID>_redirects.sql.gz```
- ```./data/<WIKI_ID>/lr_<WIKI_ID>_w2vfiltered.sql.gz```

Note:  for each of the four files there will be an additional file for the checksum
- ```*.checksum``` A checksum generated from the \*.sql.gz file

#### Summary
The trained model consists of the following files:
- anchors, redirects, pageids, w2vfiltered, model
- The SQLite and pkl-files are for local querying. pkl is faster since it loads everything into memory. SQLite is slower but needs much less memory since it looks up the data on-disk.
- The MySQL-tables are used in production. They can be accessed via the staging-database on the stat-machine. For use in production, they will be imported from the published dataset-dumps.

The backtesting evaluation of the model can be inspected in the following file:
- ```./data/<WIKI_ID>/testing/<WIKI_ID>.backtest.eval.csv```: index, threshold, number_of_sentences, precision, recall \n
- The numbers of precision and recall should not be too low. One can compare with the numbers reported in previous experiments on 10+ deployed wikis ([meta](https://meta.wikimedia.org/wiki/Research:Link_recommendation_model_for_add-a-link_structured_task#Third_set_of_results_(2021-06))). For the default threshold 0.5, the precision should be around 75% (or more) and the recall should not drop below 20% so there are still enough links to generate.

## Publishing models and datasets
**Be very cautious about this step -- make sure someone in the [Growth Team](https://www.mediawiki.org/wiki/Growth/Personalized_first_day/Structured_tasks/Add_a_link) knows about the model being updated.**

This publishes the MySQL-dumps containing the trained model (and underlying datasets) so they can be used by the Link recommendation service. This requires that “training the model” was run successfully.

```
WIKI_ID=<WIKI_ID> ./publish-datasets.sh
```
For example, for the Czech Wikipedia use \<WIKI_ID\>=cswiki

All relevant files will be copied to ```/srv/published/datasets/one-off/research-mwaddlink/<WIKI_ID>/```:
- ```<WIKI_ID>.pageids.sqlite.checksum```
- ```<WIKI_ID>.w2vfiltered.sqlite.gz```
- ```lr_<WIKI_ID>_redirects.sql.gz```
- ```<WIKI_ID>.anchors.sqlite.checksum```
- ```<WIKI_ID>.pageids.sqlite.gz```
- ```lr_<WIKI_ID>_anchors.sql.gz```
- ```lr_<WIKI_ID>_redirects.sql.gz.checksum```
- ```<WIKI_ID>.anchors.sqlite.gz```
- ```<WIKI_ID>.redirects.sqlite.checksum```
- ```lr_<WIKI_ID>_anchors.sql.gz.checksum```
- ```lr_<WIKI_ID>_w2vfiltered.sql.gz```
- ```<WIKI_ID>.linkmodel.json```
- ```<WIKI_ID>.redirects.sqlite.gz```
- ```lr_<WIKI_ID>_pageids.sql.gz```
- ```lr_<WIKI_ID>_w2vfiltered.sql.gz.checksum```
- ```<WIKI_ID>.linkmodel.json.checksum```
- ```<WIKI_ID>.w2vfiltered.sqlite.checksum```
- ```lr_<WIKI_ID>_pageids.sql.gz.checksum```

The datasets from the trained model (see training) get published in https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/. The production instance imports the tables from there.

## Unpublishing the model/datasets
**Be very cautious about this step -- make sure someone in the [Growth Team](https://www.mediawiki.org/wiki/Growth/Personalized_first_day/Structured_tasks/Add_a_link) knows about the model being removed.**

To unpublish a given wiki's datasets from the [published datasets repo](https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/) and delist it from from the [index](https://analytics.wikimedia.org/published/datasets/one-off/research-mwaddlink/wikis.txt) run:

```
WIKI_ID=<WIKI_ID> ./unpublish-datasets.sh
```

## Querying the model
Once the model has been trained, one can make queries to generate link recommendations for individual articles.

Locally, the easiest way is to use the SQLite-files for querying. For example, to get the recommendations for the article [Garnet Carter in German Wikipedia](https://de.wikipedia.org/wiki/Garnet_Carter) (dewiki):
- SQLite-backend
``` bash
DB_BACKEND=sqlite \
flask mwaddlink query --page-title Garnet_Carter --project=wikipedia --wiki-domain=de --revision=0
```
- MySQL-backend
``` bash
DB_USER=research \
DB_BACKEND=mysql \
DB_DATABASE=staging \
DB_HOST=staging-db-analytics.eqiad.wmnet \
DB_PORT=3350 DB_READ_DEFAULT_FILE=/etc/mysql/conf.d/analytics-research-client.cnf \
flask mwaddlink query --page-title Garnet_Carter --project=wikipedia --wiki-domain=de --revision=0
```
Alternatively, you can query the model using the MySQL-tables. Note that this requires that the checksums are available as MySQL-tables. This happens only when calling ```load-dataset.py```. This step is typically only performed in production and not on stat1008. Thus, by default this will not work at this stage.

- HTTP API
``` bash
DB_USER=root \
DB_PASSWORD=password \
DB_PORT=3306 \
DB_HOST=127.0.0.1 \
DB_DATABASE=addlink \
DB_BACKEND=mysql \
MEDIAWIKI_API_URL=https://my.wiki.url/w/rest.php \
MEDIAWIKI_API_BASE_URL=https://my.wiki.url/w/ \
FLASK_APP=app \
FLASK_DEBUG=1 \
flask run
```

In production, we use `gunicorn` to serve the Flask app, and the MEDIAWIKI_API_URL parameter is omitted, making the app
select the right Wikipedia URL automatically.

The Swagger UI is enabled resulting in API docs at `http://localhost:5000{$URL_PREFIX}apidocs`.

The production URL for the Swagger docs is https://api.wikimedia.org/service/linkrecommendation/apidocs/

## Development

Run lint checks with `flake8`: `.venv_query/bin/flake8` or `tox`.

Format your code with [`black`](https://pypi.org/project/black/).

You can use the environment variable FLASK_DEBUG=1 to make the service run in debug mode (for nice error traces) and FLASK_PROFILING=1 to log detailed profiling data.

## Docker Compose

There is a Docker Compose configuration for running the service locally. Run `docker-compose up -d` then use `docker-compose exec linkrecommendation [cmd]` to execute code in the application container.

You can also override the `docker-compose.yml` configuration with `docker-compose.override.yml`, here is an example to use with running tests:

```yaml
version: "3.9"
services:
  linkrecommendation:
    image: docker-registry.wikimedia.org/wikimedia/research-mwaddlink:test
    environment:
      DB_BACKEND: 'sqlite'
```

Note that on macOS hosts there is currently an issue with XGBoost when loading the JSON model:

```
xgboost.core.XGBoostError: [09:00:14] ../src/common/json.cc:449: Unknown construct, around character position: 71
```

See [T275358](https://phabricator.wikimedia.org/T275358) for more information.
