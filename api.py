from flask import Flask, request, jsonify, redirect
from flasgger import Swagger, swag_from, validate
import json_logging
import logging
import os
from sys import stdout
from src.DatasetLoader import DatasetLoader
from src.query import Query
from dotenv import load_dotenv

app = Flask(__name__)
swag = Swagger(app)
json_logging.init_flask(enable_json=True)
json_logging.init_request_instrument(app)
logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(stdout))

load_dotenv()


@app.route("/", methods=["GET"])
def main():
    return redirect("/apidocs")


@swag_from("linkrecommendation.yml")
@app.route("/query", methods=["POST"])
def query():
    data = request.json
    validate(data, "Input", "linkrecommendation.yml")
    datasetloader = DatasetLoader(
        backend=os.environ.get("DB_BACKEND"), wiki_id=data["wiki_id"]
    )
    query_instance = Query(logger, datasetloader)
    return jsonify(
        query_instance.run(
            wikitext=data["wikitext"],
            revid=data["revid"],
            pageid=data["pageid"],
            threshold=data["threshold"],
            wiki_id=data["wiki_id"],
            page_title=data["page_title"],
        )
    )
