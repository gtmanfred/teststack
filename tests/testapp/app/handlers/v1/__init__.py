from flask import Blueprint

from . import health

blueprint = Blueprint('v1', __name__, url_prefix='/api/v1')
blueprint.add_url_rule('/health', view_func=health.Health.as_view('health'))
