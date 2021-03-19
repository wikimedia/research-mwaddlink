from flask import Flask, request, jsonify, redirect
from flasgger import Swagger, validate
import json_logging
import logging
import os
from werkzeug.middleware.profiler import ProfilerMiddleware

from sys import stdout
from src.DatasetLoader import DatasetLoader
from src.scripts.utils import getPageDict, normalise_title
from src.query import Query
from src.LogstashAwareJSONRequestLogFormatter import (
    LogstashAwareJSONRequestLogFormatter,
)
from dotenv import load_dotenv

app = Flask(__name__)
# Debug mode also enables profiling.
if os.getenv("FLASK_DEBUG"):
    app.config["PROFILE"] = True
    app.wsgi_app = ProfilerMiddleware(
        app.wsgi_app,
        restrictions=[100],
        sort_by=["cumulative"],
    )
app.config["JSON_AS_ASCII"] = False
is_swagger_ui_enabled = os.environ.get("SWAGGER_UI_ENABLED")
swagger_ui_url_prefix = os.environ.get("SWAGGER_UI_URL_PREFIX", "/")
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
    "url_prefix": swagger_ui_url_prefix,
    # JSON spec is always enabled, UI is enabled only for external traffic release
    "swagger_ui": is_swagger_ui_enabled,
    "specs_route": "/apidocs/",
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
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(stdout))

load_dotenv()


@app.route("/", methods=["GET"])
def main():
    if is_swagger_ui_enabled:
        return redirect("%sapidocs" % swagger_ui_url_prefix)
    return "Please see https://api.wikimedia.org/wiki/API_reference/Service/Link_Recommendation for documentation."


@app.route(
    "/v1/linkrecommendations/<string:project>/<string:wiki_domain>/<string:page_title>",
    methods=["POST", "GET"],
)
def query(project, wiki_domain, page_title):
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
        return (
            "Unable to process request for %s/%s. Project/domain pairs that can be processed by the service: \n- %s\n"
            % (project, wiki_domain, "\n- ".join(sorted(valid_domains))),
            400,
        )

    if request.method == "POST":
        data = request.json
        validate(data, "Input", "swagger/linkrecommendations.yml")
    else:
        try:
            data = getPageDict(
                title=page_title,
                project=project,
                wiki_domain=wiki_domain,
                api_url=os.environ.get("MEDIAWIKI_API_URL"),
                proxy_api_url=os.environ.get("MEDIAWIKI_PROXY_API_URL"),
            )
        except KeyError as e:
            if e.args[0] == "revisions":
                return "Page not found: %s" % page_title, 404
            raise e

    # FIXME: We're supposed to be able to read these defaults from the Swagger spec
    data["threshold"] = float(request.args.get("threshold", 0.5))
    data["max_recommendations"] = int(request.args.get("max_recommendations", 15))

    query_instance = Query(logger, datasetloader)
    return jsonify(
        query_instance.run(
            wikitext=data["wikitext"],
            revid=data["revid"],
            pageid=data["pageid"],
            threshold=data["threshold"],
            wiki_id=wiki_id,
            page_title=normalise_title(page_title),
            max_recommendations=data["max_recommendations"],
        )
    )


@app.route("/healthz", methods=["GET"])
def healthz():
    """
    Kubernetes will use this endpoint to know if it should route traffic to the application.
    @return:
    An empty string and a HTTP 200 response.
    """
    return "", 200
