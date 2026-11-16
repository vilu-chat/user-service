import uuid

import pytest

from tests.conftest import ANNA, BOB

ME = "/api/v1/users/me"


def me(client, as_user, user):
    return client.get(ME, headers=as_user(user)).get_json()


def test_patch_me_changes_only_the_callers_row(client, as_user):
    client.get(ME, headers=as_user(ANNA, name="Anna"))
    client.get(ME, headers=as_user(BOB, name="Bob"))
    bob_before = me(client, as_user, BOB)

    client.patch(ME, json={"display_name": "Anna 2", "bio": "mine"}, headers=as_user(ANNA))

    assert me(client, as_user, BOB) == bob_before
    assert me(client, as_user, ANNA)["bio"] == "mine"


def test_the_target_user_comes_from_the_token_never_from_the_body(client, as_user):
    client.get(ME, headers=as_user(ANNA, name="Anna"))
    client.get(ME, headers=as_user(BOB, name="Bob"))
    bob_before = me(client, as_user, BOB)

    for body in ({"id": str(BOB), "bio": "pwned"}, {"user_id": str(BOB), "bio": "pwned"}):
        assert client.patch(ME, json=body, headers=as_user(ANNA)).status_code == 422
    assert me(client, as_user, BOB) == bob_before
    assert me(client, as_user, ANNA)["bio"] is None


def test_deleting_me_deletes_only_the_caller(client, as_user, db_user):
    client.get(ME, headers=as_user(ANNA, name="Anna"))
    client.get(ME, headers=as_user(BOB, name="Bob"))
    client.delete(ME, headers=as_user(ANNA))
    assert db_user(ANNA).deleted_at is not None
    assert db_user(BOB).deleted_at is None
    assert client.get(ME, headers=as_user(BOB)).status_code == 200


def test_there_is_no_endpoint_to_change_or_delete_someone_elses_row(client, as_user, db_user):
    client.get(ME, headers=as_user(BOB, name="Bob"))
    before = me(client, as_user, BOB)
    url = f"/api/v1/users/{BOB}"
    for method in ("patch", "put", "delete", "post"):
        response = getattr(client, method)(url, json={"bio": "pwned"}, headers=as_user(ANNA))
        assert response.status_code == 405, method
    assert me(client, as_user, BOB) == before
    assert db_user(BOB).deleted_at is None


def test_reading_another_user_exposes_only_the_public_fields(client, as_user):
    client.get(ME, headers=as_user(BOB, name="Bob"))
    client.patch(ME, json={"locale": "sv", "timezone": "Europe/Stockholm"}, headers=as_user(BOB))
    body = client.get(f"/api/v1/users/{BOB}", headers=as_user(ANNA)).get_json()
    for private in ("locale", "timezone", "created_at", "avatar_key", "deleted_at", "updated_at"):
        assert private not in body


def test_lookup_exposes_only_the_public_fields(client, as_user):
    client.get(ME, headers=as_user(BOB, name="Bob"))
    client.patch(ME, json={"locale": "sv"}, headers=as_user(BOB))
    (item,) = client.post("/api/v1/users/lookup", json={"ids": [str(BOB)]}, headers=as_user(ANNA)).get_json()
    assert "locale" not in item and "created_at" not in item


@pytest.mark.parametrize(
    "method,url",
    [
        ("get", ME),
        ("patch", ME),
        ("delete", ME),
        ("get", f"/api/v1/users/{uuid.uuid4()}"),
        ("post", "/api/v1/users/lookup"),
    ],
)
def test_every_endpoint_requires_a_token(client, method, url):
    assert getattr(client, method)(url, json={}).status_code == 401
