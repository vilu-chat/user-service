from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint

from app.auth import require_auth
from app.schemas import UserLookupSchema, UserMeSchema, UserSchema, UserSearchArgsSchema, UserUpdateSchema
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
        return user_service.get_or_create_me(g.current_user_id, g.claims.get("name"), g.current_username)

    @require_auth
    @blp.doc(security=SECURITY)
    @blp.arguments(UserUpdateSchema)
    @blp.response(200, UserMeSchema)
    def patch(self, data):
        """Update own profile; only the fields sent are changed."""
        return user_service.update_me(g.current_user_id, g.claims.get("name"), data, g.current_username)

    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(204)
    def delete(self):
        """Soft-delete the account. Idempotent."""
        user_service.delete_me(g.current_user_id, g.claims.get("name"), g.current_username)


@blp.route("/lookup")
class Lookup(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.arguments(UserLookupSchema)
    @blp.response(200, UserSchema(many=True))
    def post(self, data):
        """Bulk lookup (max 100 ids). Unknown and deleted users are omitted."""
        return user_service.lookup(data["ids"])


@blp.route("/search")
class Search(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.arguments(UserSearchArgsSchema, location="query")
    @blp.response(200, UserSchema(many=True))
    def get(self, args):
        """Find users by username prefix (3 to 64 characters). No cursor; at most 20 results."""
        return user_service.search(g.current_user_id, args["q"], args["limit"])


@blp.route("/<uuid:user_id>")
class UserById(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(200, UserSchema)
    def get(self, user_id):
        """Public profile of another user."""
        return user_service.get_public(user_id)
