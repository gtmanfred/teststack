from flask import current_app
from flask import jsonify
from flask.views import MethodView

from app.database import db


def health_database_status():
    try:
        # to check database we will execute raw query
        db.session.execute("SELECT 1")
    except Exception as e:
        return False
    return True


def health_cache_status():
    for cache, backend in current_app.extensions["cache"].items():
        try:
            backend._read_client.keys()
        except Exception as e:
            return False
    return True


class Health(MethodView):
    def get(self):
        database = health_database_status()
        cache = health_cache_status()
        return jsonify(
            {
                "status": database and cache,
                "database": database,
                "cache": cache,
            }
        )
