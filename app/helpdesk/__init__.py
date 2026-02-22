from flask import Blueprint

helpdesk_bp = Blueprint("helpdesk", __name__, template_folder="templates")

from . import routes  # noqa
