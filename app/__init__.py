from pathlib import Path

from flask import Flask
from flask_cors import CORS
from jwt import PyJWKClient

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import api, db, migrate

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    db.init_app(app)
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR))
    api.init_app(app)
    if app.config["CORS_ALLOWED_ORIGINS"]:
        # Bearer tokens, not cookies: no credentials. Only /api/*; health and docs stay without CORS.
        CORS(
            app,
            resources={r"/api/*": {"origins": app.config["CORS_ALLOWED_ORIGINS"]}},
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )
    api.spec.components.security_scheme(
        "bearerAuth", {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    )
    register_error_handlers(app)

    # Fetches and caches the JWKS lazily (first token), and refetches once on an unknown kid.
    app.extensions["jwk_client"] = PyJWKClient(app.config["KEYCLOAK_JWKS_URL"])

    from app import models  # noqa: F401  (registers models with db.metadata)
    from app.blueprints.health import blp as health_blp
    from app.blueprints.relations import blp as relations_blp
    from app.blueprints.users import blp as users_blp

    api.register_blueprint(health_blp)
    api.register_blueprint(users_blp)
    api.register_blueprint(relations_blp)

    return app
