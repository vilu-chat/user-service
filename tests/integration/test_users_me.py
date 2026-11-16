import uuid

from sqlalchemy import func, select

from app.extensions import db
from app.models import User
from app.schemas import UserMeSchema

URL = "/api/v1/users/me"


def count_users(app):
    with app.app_context():
        return db.session.scalar(select(func.count()).select_from(User))


def test_first_call_creates_row_and_second_returns_same_row(app, client, auth_header):
    sub = str(uuid.uuid4())
    assert count_users(app) == 0

    first = client.get(URL, headers=auth_header(sub=sub, name="Anna Andersson"))
    assert first.status_code == 200
    assert first.get_json()["id"] == sub
    assert first.get_json()["display_name"] == "Anna Andersson"
    assert count_users(app) == 1

    second = client.get(URL, headers=auth_header(sub=sub, name="A Different Name"))
    assert second.status_code == 200
    assert second.get_json() == first.get_json()  # same row; name claim is only used on creation
    assert count_users(app) == 1


def test_display_name_falls_back_to_user(client, auth_header):
    response = client.get(URL, headers=auth_header(name=None))
    assert response.status_code == 200
    assert response.get_json()["display_name"] == "User"


def test_response_contains_only_user_me_schema_fields(client, auth_header):
    response = client.get(URL, headers=auth_header())
    body = response.get_json()
    allowed = set(UserMeSchema().fields)
    assert set(body) <= allowed
    assert {"id", "display_name", "created_at", "avatar_url"} <= set(body)
    assert body["avatar_url"] is None
    for internal in ("avatar_key", "avatar_version", "updated_at", "deleted_at"):
        assert internal not in body
