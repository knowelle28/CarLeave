from flask import Blueprint

cars_bp = Blueprint("cars", __name__, template_folder="templates")

from . import routes
