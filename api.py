from flask import Flask, request, jsonify, redirect
from flasgger import Swagger, swag_from, validate
import json_logging
import logging
import os
from sys import stdout
from src.DatasetLoader import DatasetLoader
from src.scripts.utils import getPageDict, normalise_title
from src.query import Query
from src.LogstashAwareJSONRequestLogFormatter import (
    LogstashAwareJSONRequestLogFormatter,
)
from dotenv import load_dotenv

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
swag = Swagger(app)
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
    return redirect("/apidocs")


@swag_from("swagger/linkrecommendations.post.yml", methods=["POST"])
@swag_from("swagger/linkrecommendations.get.yml", methods=["GET"])
@app.route(
    "/v0/linkrecommendations/<string:wiki_id>/<string:page_title>",
    methods=["POST", "GET"],
)
def query(wiki_id, page_title):
    if request.method == "POST":
        data = request_data = request.json
        validate(data, "Input", "swagger/linkrecommendations.post.yml")
    else:
        data = getPageDict(page_title, wiki_id)
        request_data = request.args

    # FIXME: We're supposed to be able to read these defaults from the Swagger spec
    data["threshold"] = float(request_data.get("threshold", 0.5))
    data["max_recommendations"] = int(request_data.get("max_recommendations", 15))

    datasetloader = DatasetLoader(backend=os.environ.get("DB_BACKEND"), wiki_id=wiki_id)

    try:
        datasetloader.get_model_path()
    except RuntimeError:
        return "Unable to load model for %s!" % wiki_id, 400

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
