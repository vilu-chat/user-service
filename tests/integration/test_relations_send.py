import uuid

from conftest import ANNA, BOB, CECILIA


def _put(client, as_user, caller, other):
    return client.put(f"/api/v1/users/me/relations/{other}", headers=as_user(caller))


def test_send_creates_pending_row(client, as_user, make_user, relation_rows):
    make_user(BOB, username="bob")
    response = _put(client, as_user, ANNA, BOB)
    assert response.status_code == 201
    body = response.get_json()
    assert body["other_user_id"] == str(BOB)
    assert body["kind"] == "pending"
    assert body["direction"] == "outgoing"
    assert body["user"]["username"] == "bob"
    assert relation_rows() == [(ANNA, BOB, "pending")]


def test_send_creates_the_callers_profile(client, as_user, make_user, db_user):
    make_user(BOB, username="bob")
    _put(client, as_user, ANNA, BOB)
    assert db_user(ANNA) is not None


def test_send_to_self_is_400(client, as_user):
    assert _put(client, as_user, ANNA, ANNA).status_code == 400


def test_send_to_unknown_user_is_404(client, as_user, relation_rows):
    assert _put(client, as_user, ANNA, uuid.uuid4()).status_code == 404
    assert relation_rows() == []


def test_send_to_deleted_user_is_404(client, as_user, make_user):
    make_user(BOB, username="bob", deleted=True)
    assert _put(client, as_user, ANNA, BOB).status_code == 404


def test_already_contacts_is_409(client, as_user, make_user, make_relation):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    make_relation(ANNA, BOB, "contact")
    make_relation(BOB, ANNA, "contact")
    assert _put(client, as_user, ANNA, BOB).status_code == 409
    assert _put(client, as_user, BOB, ANNA).status_code == 409


def test_already_sent_is_409(client, as_user, make_user, relation_rows):
    make_user(BOB, username="bob")
    assert _put(client, as_user, ANNA, BOB).status_code == 201
    assert _put(client, as_user, ANNA, BOB).status_code == 409
    assert relation_rows() == [(ANNA, BOB, "pending")]


def test_they_already_sent_you_one_is_409(client, as_user, make_user, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    assert _put(client, as_user, BOB, ANNA).status_code == 201
    assert _put(client, as_user, ANNA, BOB).status_code == 409
    assert relation_rows() == [(BOB, ANNA, "pending")]


def test_requires_auth(client):
    assert client.put(f"/api/v1/users/me/relations/{BOB}").status_code == 401


def test_deleted_caller_is_403(client, as_user, make_user):
    make_user(ANNA, username="anna", deleted=True)
    make_user(BOB, username="bob")
    response = _put(client, as_user, ANNA, BOB)
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "account_deleted"
