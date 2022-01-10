import click
from flask import (
    Flask,
    request,
    jsonify,
    redirect,
    url_for,
    has_app_context,
    has_request_context,
)
from flasgger import Swagger, validate
import json_logging
import logging
import json
import os
import subprocess
from werkzeug.routing import PathConverter
from werkzeug.middleware.profiler import ProfilerMiddleware

from sys import stdout
from src.ClickProfiler import ClickProfiler
from src.DatasetLoader import DatasetLoader
from src.scripts.utils import normalise_title
from src.MediaWikiApi import MediaWikiApi
from src.query import Query
from src.LogstashAwareJSONRequestLogFormatter import (
    LogstashAwareJSONRequestLogFormatter,
)
from dotenv import load_dotenv


class ProxyPassMiddleware(object):
    """Simplified version of flask-reverse-proxy-fix"""

    def __init__(self, app, url_prefix):
        self.app = app
        self.url_prefix = url_prefix

    def __call__(self, environ, start_response):
        environ["SCRIPT_NAME"] = self.url_prefix
        path_info = environ["PATH_INFO"]
        if path_info.startswith(self.url_prefix):
            environ["PATH_INFO"] = path_info[len(self.url_prefix) :]
        return self.app(environ, start_response)


class TitleConverter(PathConverter):
    # copy of $wgLegalTitleChars in MediaWiki's DefaultSettings.php,
    # slightly modified since it will be applied to a Unicode string
    regex = u"[ %!\"$&'()*,\\-.\\/0-9:;=?@A-Z\\\\^_`a-z~\u0080-\U0010FFFF+]+"


app = Flask(__name__)
if os.getenv("FLASK_PROFILE"):
    app.config["PROFILE"] = True
    app.wsgi_app = ProfilerMiddleware(
        app.wsgi_app,
        restrictions=[100],
        sort_by=["cumulative"],
    )
app.config["JSON_AS_ASCII"] = False
url_prefix = os.environ.get("URL_PREFIX", "/")
if url_prefix != "/":
    app.wsgi_app = ProxyPassMiddleware(app.wsgi_app, url_prefix)
app.url_map.converters["title"] = TitleConverter

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec_1",
            "route": "/apispec_1.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "url_prefix": None,
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "basePath": url_prefix,
}
swag = Swagger(
    app,
    template_file="swagger/linkrecommendations.yml",
    config=swagger_config,
)
json_logging.init_flask(enable_json=True)
json_logging.init_request_instrument(
    app=app, custom_formatter=LogstashAwareJSONRequestLogFormatter
)
logger = logging.getLogger("logger")
logger.setLevel(os.environ.get("FLASK_LOGLEVEL", logging.WARNING))
logger.addHandler(logging.StreamHandler(stdout))

load_dotenv()


@app.route("/", methods=["GET"])
def main():
    return redirect(url_for("flasgger.apidocs"))


@app.cli.command("query")
@click.option(
    "--page-title", type=str, help="Page title to use in the query", required=True
)
@click.option(
    "--project",
    default="wikipedia",
    required=True,
    type=str,
    help="Wiki project for which to get recommendations (e.g. 'wikipedia', 'wiktionary'",
)
@click.option(
    "--wiki-domain",
    type=str,
    required=True,
    help="Wiki domain for which to get recommendations (e.g. 'cs')",
)
@click.option(
    "--threshold",
    default=0.5,
    required=False,
    type=float,
    help="Threshold value for links to be recommended",
)
@click.option(
    "--max-recommendations",
    default=15,
    type=int,
    required=False,
    help="Maximum number of link recommendations to query (set to -1 for all)",
)
@click.pass_context
def cli_query(ctx: click.Context, *args, **kwargs):
    if os.getenv("FLASK_PROFILE"):
        ClickProfiler(restrictions=[100], sort_by=["cumulative"]).profile(ctx)
    query(*args, **kwargs)


@app.route(
    "/v1/linkrecommendations/<string:project>/<string:wiki_domain>/<title:page_title>",
    methods=["POST", "GET"],
    merge_slashes=False,
)
def query(project, wiki_domain, page_title, threshold=None, max_recommendations=None):
    if project == "wikipedia":
        # FIXME: What we should do instead is rename the datasets to {project}{domain} e.g. wikipediafr
        # to avoid this hack
        wiki_id = "%swiki" % wiki_domain
    else:
        wiki_id = "%s%s" % (wiki_domain, project)
    wiki_id = wiki_id.replace("_", "-")
    datasetloader = DatasetLoader(backend=os.environ.get("DB_BACKEND"), wiki_id=wiki_id)

    path, valid_domains = datasetloader.get_model_path()
    if not path:
        warning_message = (
            "Unable to process request for %s/%s. Project/domain pairs that can be processed by the service: \n- %s\n"
            % (project, wiki_domain, "\n- ".join(sorted(valid_domains))),
            400,
        )
        logger.warning(warning_message)
        if has_app_context():
            print(warning_message)
        return warning_message

    if has_request_context() and request.method == "POST":
        data = request.json
        validate(data, "Input", "swagger/linkrecommendations.yml")
    else:
        try:
            mw_api = MediaWikiApi(
                api_url=os.environ.get("MEDIAWIKI_API_BASE_URL"),
                proxy_api_url=os.environ.get("MEDIAWIKI_PROXY_API_BASE_URL"),
                project=project,
                wiki_domain=wiki_domain,
            )
            data = mw_api.get_article(page_title)
        except KeyError as e:
            if e.args[0] == "revisions":
                page_not_found_message = "Page not found: %s" % page_title, 404
                logger.warning(page_not_found_message)
                if has_app_context():
                    print(page_not_found_message)
                return page_not_found_message
            raise e

    # FIXME: We're supposed to be able to read these defaults from the Swagger spec
    data["threshold"] = threshold or float(request.args.get("threshold", 0.5))
    data["max_recommendations"] = max_recommendations or int(
        request.args.get("max_recommendations", 15)
    )

    query_instance = Query(logger, datasetloader)
    result = query_instance.run(
        wikitext=data["wikitext"],
        revid=data["revid"],
        pageid=data["pageid"],
        threshold=data["threshold"],
        wiki_id=wiki_id,
        page_title=normalise_title(page_title),
        max_recommendations=data["max_recommendations"],
    )
    result["meta"]["application_version"] = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
        .decode("ascii")
        .strip()
    )
    response = jsonify(result)

    logger.debug(response)
    if has_app_context():
        print(json.dumps(response.get_json()))
    return response


@app.route("/healthz", methods=["GET"])
def healthz():
    """
    Kubernetes will use this endpoint to know if it should route traffic to the application.
    @return:
    An empty string and a HTTP 200 response.
    """
    return "", 200


if __name__ == "__main__":
    query()
