import MySQLdb
import os
from dotenv import load_dotenv

load_dotenv()


def get_mysql_connection():
    connection_dict = get_connection_dict()
    return MySQLdb.connect(**connection_dict)


def get_connection_dict() -> dict:
    items = {
        "user": os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASSWORD"),
        "host": os.environ.get("DB_HOST"),
        "database": os.environ.get("DB_DATABASE"),
        "port": int(os.environ.get("DB_PORT", 3306)),
        "read_default_file": os.environ.get("DB_READ_DEFAULT_FILE"),
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    return {k: v for k, v in items.items() if v is not None}


def import_model_to_table(cursor: object, linkmodel: str, wiki_id: str):
    """
    Import the link model to the database table.
    Unlike other datasets, where we use a single table per dataset (e.g. cswiki_anchors, arwiki_anchors), the link
    model is stored in a single table with a key for the wiki ID and the value is the JSON content of the model.
    :param cursor:
    :param linkmodel:
    :param wiki_id:
    """
    cursor.execute(
        "DELETE FROM lr_model WHERE lookup = %s LIMIT 1",
        (wiki_id,),
    )
    query = "INSERT INTO lr_model (lookup, value) VALUES (%s,%s)"
    cursor.execute(query, (wiki_id, linkmodel))
