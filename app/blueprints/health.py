from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

blp = Blueprint("health", __name__, description="Liveness and readiness")


@blp.route("/healthz")
class Healthz(MethodView):
    def get(self):
        """Liveness: the process is up."""
        return {"status": "ok"}


@blp.route("/readyz")
class Readyz(MethodView):
    def get(self):
        """Readiness: the database answers."""
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            abort(503, message="Database unavailable")
        return {"status": "ok"}
