import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def get_mysql_connection():
    connection_dict = get_connection_dict()
    return pymysql.connect(
        user=connection_dict["user"],
        password=connection_dict["password"],
        host=connection_dict["host"],
        database=connection_dict["database"],
        port=connection_dict["port"],
        read_default_file=connection_dict["read_default_file"],
        charset=connection_dict["charset"],
        use_unicode=connection_dict["use_unicode"],
    )


def get_connection_dict() -> dict:
    return {
        "user": os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASSWORD"),
        "host": os.environ.get("DB_HOST"),
        "database": os.environ.get("DB_DATABASE"),
        "port": int(os.environ.get("DB_PORT", 3306)),
        "read_default_file": os.environ.get("DB_READ_DEFAULT_FILE"),
        "charset": "utf8",
        "use_unicode": True,
    }
