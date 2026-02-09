# research/mwaddlink

This is the repository that backs the [Wikimedia Link Recommendation service](https://wikitech.wikimedia.org/wiki/Add_Link).

It contains code for powering the [Link Recommendation service](https://api.wikimedia.org/service/linkrecommendation/) only, not for training
the models that backs the service up.

## Model summary
The service assumes a model is already available. The trained model consists of the following files:
- anchors, redirects, pageids, w2vfiltered, model
- The SQLite and pkl-files are for local querying. pkl is faster since it loads everything into memory. SQLite is slower but needs much less memory since it looks up the data on-disk.
- The MySQL-tables are used in production. They can be accessed via the staging-database on the stat-machine. For use in production, they will be imported from the published dataset-dumps.

For WMF wikis, the models are available on [WMF Analytics](https://analytics.wikimedia.org/published/wmf-ml-models/addalink/v2).

If you are interested in code to train the models, see [Airflow ML DAGs](https://gitlab.wikimedia.org/repos/data-engineering/airflow-dags/-/tree/main/ml/dags) on GitLab.

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
flask mwaddlink query --page-title Garnet_Carter --project=wikipedia --wiki-domain=de --revision=0 --language-code de
```
Alternatively, you can query the model using the MySQL-tables. Note that this requires that the checksums are available as MySQL-tables. This happens only when calling ```load-dataset.py```. This step is typically only performed in production and not on stat1008. Thus, by default this will not work at this stage.

- HTTP API
``` bash
DB_USER=root \
DB_PASSWORD=root \
DB_PORT=3306 \
DB_HOST=127.0.0.1 \
DB_DATABASE=addlink \
DB_BACKEND=mysql \
MEDIAWIKI_API_BASE_URL=https://my.wiki.url/w/ \
FLASK_APP=app \
FLASK_DEBUG=1 \
FLASK_RUN_PORT=8000 \
flask run
```

In production, we use `gunicorn` to serve the Flask app, and the MEDIAWIKI_API_BASE_URL parameter is omitted, making the app
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