import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


class Config:
    """All settings come from environment variables, read when the object is created."""

    def __init__(self) -> None:
        self.SQLALCHEMY_DATABASE_URI = _required("SQLALCHEMY_DATABASE_URI")
        # Each gunicorn worker has its own pool (design: 3 + 2 overflow per worker).
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": int(os.environ.get("DB_POOL_SIZE", "3")),
            "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "2")),
        }

        self.KEYCLOAK_ISSUER = _required("KEYCLOAK_ISSUER")
        self.KEYCLOAK_JWKS_URL = _required("KEYCLOAK_JWKS_URL")
        self.KEYCLOAK_AUDIENCE = _required("KEYCLOAK_AUDIENCE")

        # Comma-separated exact origins allowed to call /api/* from a browser, for example
        # "https://app.example.com". Empty (default): no CORS headers (same-origin setups).
        self.CORS_ALLOWED_ORIGINS = [
            origin.strip()
            for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]

        # flask-smorest: OpenAPI spec at /openapi.json, Swagger UI at /docs
        self.API_TITLE = "User Service"
        self.API_VERSION = "v1"
        self.OPENAPI_VERSION = "3.0.3"
        self.OPENAPI_URL_PREFIX = "/"
        self.OPENAPI_JSON_PATH = "openapi.json"
        self.OPENAPI_SWAGGER_UI_PATH = "/docs"
        self.OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
