import typing

import flask
import flask_caching

from .database import db
from .handlers.v1 import blueprint as blueprint_v1


def create_app(config: typing.Dict = None) -> flask.Flask:
    app = flask.Flask(__name__)
    app.config.from_object('app.config:Config')
    if config is not None:
        app.config.update(config)
    db.init_app(app)
    flask_caching.Cache(app)
    app.register_blueprint(blueprint_v1)
    return app
