import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import load_dotenv
from flask_migrate import downgrade, upgrade
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import text

load_dotenv()

ISSUER = "http://localhost:8081/realms/chat"
AUDIENCE = "chat-api"
KID = "test-key"


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("TEST_DATABASE_URL is not set (see .env.example)", returncode=2)
    # The reset fixture truncates tables, so refuse anything that is not a test database.
    if not url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        pytest.exit("TEST_DATABASE_URL must point at a database whose name ends in _test", returncode=2)
    return url


@pytest.fixture(scope="session")
def app():
    # Hermetic config: tests never use whatever is in .env or the shell.
    os.environ["SQLALCHEMY_DATABASE_URI"] = _test_database_url()
    os.environ["KEYCLOAK_ISSUER"] = ISSUER
    os.environ["KEYCLOAK_JWKS_URL"] = "http://jwks.invalid/certs"  # never fetched, see jwks_patch
    os.environ["KEYCLOAK_AUDIENCE"] = AUDIENCE

    from app import create_app

    app = create_app()
    with app.app_context():
        downgrade(revision="base")  # start from an empty schema, which also exercises downgrade
        upgrade()
    yield app


@pytest.fixture(autouse=True)
def reset_data(app):
    yield
    from app.extensions import db

    with app.app_context():
        db.session.execute(text("TRUNCATE TABLE users, outbox_events RESTART IDENTITY CASCADE"))
        db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def jwks_patch(monkeypatch, rsa_key):
    """The JWKS lookup returns the test public key instead of calling the network."""
    jwk = RSAAlgorithm.to_jwk(rsa_key.public_key(), as_dict=True)
    jwk.update(kid=KID, use="sig", alg="RS256")
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [jwk]})


@pytest.fixture
def make_token(rsa_key):
    def _make(*, key=None, headers=None, expires_in=300, preferred_username="anna", **overrides):
        now = datetime.now(timezone.utc)
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "name": "Anna Andersson",
            "preferred_username": preferred_username,  # None leaves the claim out
            "email": "anna@example.test",
            "realm_access": {"roles": ["user"]},
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(
            claims, key or rsa_key, algorithm="RS256", headers={"kid": KID, **(headers or {})}
        )

    return _make


@pytest.fixture
def auth_header(make_token):
    def _header(**kwargs):
        return {"Authorization": f"Bearer {make_token(**kwargs)}"}

    return _header


ANNA = uuid.UUID("0b1f6a4e-5c1d-4e8a-9a57-3f2d8c1a0001")
BOB = uuid.UUID("0b1f6a4e-5c1d-4e8a-9a57-3f2d8c1a0002")
CECILIA = uuid.UUID("0b1f6a4e-5c1d-4e8a-9a57-3f2d8c1a0003")


DAVID = uuid.UUID("0b1f6a4e-5c1d-4e8a-9a57-3f2d8c1a0004")
USERNAMES = {ANNA: "anna", BOB: "bob", CECILIA: "cecilia", DAVID: "david"}


@pytest.fixture
def as_user(auth_header):
    """Headers for a given user: as_user(ANNA, name="Anna")."""

    def _headers(user_id, **claims):
        # Each user gets their own username unless the test says otherwise (None = no claim).
        claims.setdefault("preferred_username", USERNAMES.get(user_id, f"user-{user_id.hex[:8]}"))
        return auth_header(sub=str(user_id), **claims)

    return _headers


@pytest.fixture
def outbox(app):
    """outbox(event_type=None) -> list of OutboxEvent rows, oldest first."""
    from sqlalchemy import select

    from app.extensions import db
    from app.models import OutboxEvent

    def _rows(event_type=None):
        with app.app_context():
            query = select(OutboxEvent).order_by(OutboxEvent.id)
            if event_type:
                query = query.where(OutboxEvent.event_type == event_type)
            return list(db.session.scalars(query))

    return _rows


@pytest.fixture
def db_user(app):
    """db_user(user_id) -> the User row (or None), read straight from the database."""
    from app.extensions import db
    from app.models import User

    def _get(user_id):
        with app.app_context():
            user = db.session.get(User, user_id)
            if user is not None:
                db.session.expunge(user)
            return user

    return _get


@pytest.fixture
def make_user(app):
    """make_user(user_id, username=None, deleted=False, display_name=None) inserts a users row directly."""
    from app.extensions import db
    from app.models import User

    def _make(user_id, username=None, deleted=False, display_name=None):
        with app.app_context():
            db.session.add(
                User(
                    id=user_id,
                    username=username,
                    display_name=display_name or (username or "Someone").title(),
                    deleted_at=datetime.now(timezone.utc) if deleted else None,
                )
            )
            db.session.commit()
        return user_id

    return _make


@pytest.fixture
def make_relation(app):
    """make_relation(user_id, other_user_id, kind="pending", created_at=None) inserts a user_relations row."""
    from app.extensions import db
    from app.models import UserRelation

    def _make(user_id, other_user_id, kind="pending", created_at=None):
        with app.app_context():
            row = UserRelation(user_id=user_id, other_user_id=other_user_id, kind=kind)
            if created_at is not None:
                row.created_at = created_at
            db.session.add(row)
            db.session.commit()

    return _make


@pytest.fixture
def relation_rows(app):
    """relation_rows() -> sorted (user_id, other_user_id, kind) tuples straight from the database."""
    from sqlalchemy import select

    from app.extensions import db
    from app.models import UserRelation

    def _rows():
        with app.app_context():
            rows = db.session.execute(select(UserRelation.user_id, UserRelation.other_user_id, UserRelation.kind))
            return sorted((u, o, k) for u, o, k in rows)

    return _rows
