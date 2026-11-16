from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint

from app.auth import require_auth
from app.schemas import UserLookupSchema, UserMeSchema, UserSchema, UserUpdateSchema
from app.services import user_service

blp = Blueprint("users", __name__, url_prefix="/api/v1/users", description="Profiles")

SECURITY = [{"bearerAuth": []}]


@blp.route("/me")
class Me(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(200, UserMeSchema)
    def get(self):
        """Own profile; creates the row on the first call."""
        return user_service.get_or_create_me(g.current_user_id, g.claims.get("name"))

    @require_auth
    @blp.doc(security=SECURITY)
    @blp.arguments(UserUpdateSchema)
    @blp.response(200, UserMeSchema)
    def patch(self, data):
        """Update own profile; only the fields sent are changed."""
        return user_service.update_me(g.current_user_id, g.claims.get("name"), data)

    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(204)
    def delete(self):
        """Soft-delete the account. Idempotent."""
        user_service.delete_me(g.current_user_id, g.claims.get("name"))


@blp.route("/lookup")
class Lookup(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.arguments(UserLookupSchema)
    @blp.response(200, UserSchema(many=True))
    def post(self, data):
        """Bulk lookup (max 100 ids). Unknown and deleted users are omitted."""
        return user_service.lookup(data["ids"])


@blp.route("/<uuid:user_id>")
class UserById(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(200, UserSchema)
    def get(self, user_id):
        """Public profile of another user."""
        return user_service.get_public(user_id)
