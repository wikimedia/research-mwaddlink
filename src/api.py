from flask import Flask, request
import json_logging
import logging
from sys import stdout
from src.query import Query
from webargs import fields
from webargs.flaskparser import parser


app = Flask(__name__)
json_logging.init_flask(enable_json=True)
json_logging.init_request_instrument(app)
logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(stdout))


@app.route('/', methods=['GET'])
def main():
    return 'TODO: Some landing page or API docs.'


@app.route('/query', methods=['POST'])
def query():
    query_instance = Query(logger)
    query_args = {
        "wikitext": fields.Str(required=True),
        "revid": fields.Int(required=True),
        "pageid": fields.Int(required=True),
        "threshold": fields.Float(required=True),
        "lang": fields.Str(required=True),
        "page_title": fields.Str(required=True)
    }
    args = parser.parse(query_args, request)
    return query_instance.run(
        wikitext=args["wikitext"],
        revid=args["revid"],
        pageid=args["pageid"],
        threshold=args["threshold"],
        lang=args["lang"],
        page_title=args["page_title"]
    )
