from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint

from app.auth import require_auth
from app.schemas import RelationListArgsSchema, RelationPageSchema, RelationSchema
from app.services import relation_service

blp = Blueprint(
    "relations", __name__, url_prefix="/api/v1/users/me/relations", description="Contacts and requests"
)

SECURITY = [{"bearerAuth": []}]


def _caller() -> tuple:
    return g.current_user_id, g.claims.get("name"), g.current_username


@blp.route("")
class Relations(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.arguments(RelationListArgsSchema, location="query")
    @blp.response(200, RelationPageSchema)
    def get(self, args):
        """Contacts (default) or pending requests; newest first, keyset-paginated."""
        user_id, name, username = _caller()
        return relation_service.list_mine(
            user_id,
            username,
            name,
            kind=args["kind"],
            direction=args["direction"],
            limit=args["limit"],
            cursor=args.get("cursor"),
        )


@blp.route("/<uuid:other_user_id>")
class RelationById(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(201, RelationSchema)
    def put(self, other_user_id):
        """Send a contact request (no body)."""
        user_id, name, username = _caller()
        return relation_service.send(user_id, other_user_id, name, username)

    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(204)
    def delete(self, other_user_id):
        """Remove a contact, cancel your own request or decline a received one. Always 204."""
        user_id, name, username = _caller()
        relation_service.remove(user_id, other_user_id, name, username)


@blp.route("/<uuid:other_user_id>/accept")
class Accept(MethodView):
    @require_auth
    @blp.doc(security=SECURITY)
    @blp.response(200, RelationSchema)
    def post(self, other_user_id):
        """Accept a received request; both users become contacts."""
        user_id, name, username = _caller()
        return relation_service.accept(user_id, other_user_id, name, username)
