import uuid
from functools import wraps

import jwt
from flask import current_app, g, request
from flask_smorest import abort

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthorized(message: str):
    abort(401, message=message, headers=_UNAUTHORIZED_HEADERS)


def _bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        _unauthorized("Missing or malformed Authorization header")
    return token.strip()


def require_auth(view):
    """Validate the bearer JWT (RS256 via JWKS, exp, iss, aud) and set g.current_user_id / g.claims."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        config = current_app.config
        try:
            signing_key = current_app.extensions["jwk_client"].get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=config["KEYCLOAK_ISSUER"],
                audience=config["KEYCLOAK_AUDIENCE"],
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            user_id = uuid.UUID(claims["sub"])
        except jwt.PyJWKClientConnectionError:
            abort(503, message="Cannot reach the identity provider's key endpoint")
        except jwt.ExpiredSignatureError:
            _unauthorized("Token has expired")
        except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
            _unauthorized("Invalid token")

        g.current_user_id = user_id
        g.claims = claims
        return view(*args, **kwargs)

    return wrapper
