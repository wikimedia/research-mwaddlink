import click
from flask import (
    Blueprint,
    Flask,
    request,
    jsonify,
    redirect,
    url_for,
    has_request_context,
)
from flasgger import Swagger, validate
import json_logging
import logging
import json
import sys
import os
import traceback
import subprocess
from werkzeug.routing import PathConverter
from werkzeug.exceptions import InternalServerError

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


load_dotenv()
blueprint = Blueprint("mwaddlink", __name__)


class InvalidAPIUsage(Exception):
    # Custom response class for API errors.
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


class TitleConverter(PathConverter):
    # copy of $wgLegalTitleChars in MediaWiki's DefaultSettings.php,
    # slightly modified since it will be applied to a Unicode string
    regex = "[ %!\"$&'()*,\\-.\\/0-9:;=?@A-Z\\\\^_`a-z~\u0080-\U0010FFFF+]+"


def create_app():
    flask_app = Flask(__name__)
    flask_app.url_map.converters["title"] = TitleConverter
    flask_app.register_blueprint(blueprint)
    flask_app.config["JSON_AS_ASCII"] = False
    url_prefix = os.environ.get("URL_PREFIX", "/")
    if url_prefix != "/":
        flask_app.wsgi_app = ProxyPassMiddleware(flask_app.wsgi_app, url_prefix)

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
    Swagger(
        flask_app,
        template_file="swagger/linkrecommendations.yml",
        config=swagger_config,
    )
    return flask_app


@blueprint.errorhandler(InvalidAPIUsage)
def invalid_api_usage(e):
    return jsonify(e.to_dict()), e.status_code


@blueprint.errorhandler(InternalServerError)
def handle_bad_request(e: InternalServerError):
    e_original = e.original_exception
    if e_original:
        logger.error(
            {
                "type": type(e_original).__name__,
                "description": str(e_original),
                "trace": traceback.format_tb(e_original.__traceback__),
            }
        )
    response = e.get_response()
    response.data = json.dumps(
        {
            "code": e.code,
            "name": e.name,
            "description": e.description,
        }
    )
    response.content_type = "application/json"
    return response


@blueprint.route("/", methods=["GET"])
def main():
    return redirect(url_for("flasgger.apidocs"))


@blueprint.cli.command("query")
@click.option(
    "--project",
    default="wikipedia",
    required=True,
    type=str,
    help="Wiki project for which to get recommendations (e.g. 'wikipedia', 'wiktionary'",
)
@click.option(
    "--wiki-domain",
    required=True,
    type=str,
    help="Wiki domain for which to get recommendations (e.g. 'cs')",
)
@click.option(
    "--page-title", type=str, help="Page title to use in the query", required=True
)
@click.option(
    "--revision",
    required=False,
    type=int,
    help="Page revision (defaults to latest)",
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
    required=False,
    type=int,
    help="Maximum number of link recommendations to query (set to -1 for all)",
)
@click.option(
    "--sections-to-exclude",
    default=[],
    required=False,
    type=str,
    multiple=True,
    help="Section title to exclude from link suggestion generation.",
)
@click.pass_context
def cli_query(ctx: click.Context, *args, **kwargs):
    if os.getenv("FLASK_PROFILE"):
        ClickProfiler(restrictions=[100], sort_by=["cumulative"]).profile(ctx)
    query(*args, **kwargs)


@blueprint.route(
    "/v1/linkrecommendations/<string:project>/<string:wiki_domain>/<title:page_title>",
    methods=["POST", "GET"],
    merge_slashes=False,
)
def query(
    project,
    wiki_domain,
    page_title,
    revision=None,
    threshold=None,
    max_recommendations=None,
    sections_to_exclude=None,
):
    if sections_to_exclude is None:
        sections_to_exclude = []
    if project == "wikipedia":
        # FIXME: What we should do instead is rename the datasets to {project}{domain} e.g. wikipediafr
        # to avoid this hack
        wiki_id = "%swiki" % wiki_domain
    else:
        wiki_id = "%s%s" % (wiki_domain, project)
    wiki_id = wiki_id.replace("_", "-")
    revision = revision or request.args.get("revision", 0, int)
    datasetloader = DatasetLoader(
        backend=os.environ.get("DB_BACKEND"), wiki_id=wiki_id, data_dir=app.root_path
    )

    path, valid_domains = datasetloader.get_model_path()
    if not path:
        warning_message = "Unable to process request for %s/%s" % (project, wiki_domain)
        logger.warning(warning_message)
        if not has_request_context():
            print(warning_message)
        raise InvalidAPIUsage(
            warning_message,
            status_code=400,
            payload={"valid_project_domain_pairs": valid_domains},
        )

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
            data = mw_api.get_article(page_title, revision=revision)
            if revision:
                data["revid"] = int(revision)
        except KeyError as e:
            if e.args[0] == "revisions":
                page_not_found_message = "Page not found: %s" % page_title
                logger.warning(page_not_found_message)
                if not has_request_context():
                    print(page_not_found_message)
                raise InvalidAPIUsage(message=page_not_found_message, status_code=404)
            raise e

    # FIXME: We're supposed to be able to read these defaults from the Swagger spec
    if has_request_context():
        # FIXME use POST data but fall back to GET data for migration period
        if "sections_to_exclude" not in data:
            data["sections_to_exclude"] = request.args.getlist("sections_to_exclude")
    else:
        data["sections_to_exclude"] = sections_to_exclude
    data["threshold"] = threshold or float(request.args.get("threshold", 0.5))
    data["max_recommendations"] = max_recommendations or int(
        request.args.get("max_recommendations", 15)
    )

    query_instance = Query(logger, datasetloader)
    result = query_instance.run(
        wikitext=data["wikitext"],
        revid=int(data["revid"]),
        pageid=data["pageid"],
        threshold=data["threshold"],
        wiki_id=wiki_id,
        page_title=normalise_title(page_title),
        max_recommendations=data["max_recommendations"],
        # Cap the list of sections to exclude at 25.
        sections_to_exclude=data["sections_to_exclude"][:25],
    )
    result["meta"]["application_version"] = (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
        .decode("ascii")
        .strip()
    )
    response = jsonify(result)

    logger.debug(response)
    if not has_request_context():
        print(json.dumps(response.get_json(), indent=4))
    return response


@blueprint.route("/healthz", methods=["GET"])
def healthz():
    """
    Kubernetes will use this endpoint to know if it should route traffic to the application.
    @return:
    An empty string and a HTTP 200 response.
    """
    return "", 200


app = create_app()
json_logging.init_flask(enable_json=True)
json_logging.init_request_instrument(
    app=app, custom_formatter=LogstashAwareJSONRequestLogFormatter
)
logger = logging.getLogger("logger")
loglevel = os.environ.get("FLASK_LOGLEVEL", logging.WARNING)
logger.setLevel(loglevel)
json_logging.get_request_logger().setLevel(loglevel)
logger.addHandler(logging.StreamHandler(sys.stdout))


if __name__ == "__main__":
    query()
