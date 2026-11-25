import uuid

from conftest import ANNA, BOB, CECILIA


def _accept(client, as_user, caller, other):
    return client.post(f"/api/v1/users/me/relations/{other}/accept", headers=as_user(caller))


def _put(client, as_user, caller, other):
    return client.put(f"/api/v1/users/me/relations/{other}", headers=as_user(caller))


def test_accept_creates_two_contact_rows(client, as_user, make_user, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    _put(client, as_user, ANNA, BOB)
    response = _accept(client, as_user, BOB, ANNA)
    assert response.status_code == 200
    body = response.get_json()
    assert body["other_user_id"] == str(ANNA)
    assert body["kind"] == "contact"
    assert body["direction"] is None
    assert body["user"]["username"] == "anna"
    assert relation_rows() == sorted([(ANNA, BOB, "contact"), (BOB, ANNA, "contact")])


def test_accept_is_idempotent(client, as_user, make_user, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    _put(client, as_user, ANNA, BOB)
    _accept(client, as_user, BOB, ANNA)
    before = relation_rows()
    assert _accept(client, as_user, BOB, ANNA).status_code == 200
    # The original sender is a contact too, so accepting from their side is a no-op as well.
    assert _accept(client, as_user, ANNA, BOB).status_code == 200
    assert relation_rows() == before


def test_accept_without_request_is_404(client, as_user, make_user, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    assert _accept(client, as_user, BOB, ANNA).status_code == 404
    assert _accept(client, as_user, BOB, uuid.uuid4()).status_code == 404
    assert _accept(client, as_user, BOB, BOB).status_code == 404
    assert relation_rows() == []


def test_only_the_receiver_can_accept(client, as_user, make_user, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    make_user(CECILIA, username="cecilia")
    _put(client, as_user, ANNA, BOB)
    assert _accept(client, as_user, ANNA, BOB).status_code == 404  # the sender
    assert _accept(client, as_user, CECILIA, ANNA).status_code == 404  # a third user
    assert _accept(client, as_user, CECILIA, BOB).status_code == 404
    assert relation_rows() == [(ANNA, BOB, "pending")]


def test_accept_when_sender_is_deleted_is_404(client, as_user, make_user, make_relation, relation_rows):
    make_user(ANNA, username="anna", deleted=True)
    make_user(BOB, username="bob")
    make_relation(ANNA, BOB, "pending")
    assert _accept(client, as_user, BOB, ANNA).status_code == 404
    assert relation_rows() == [(ANNA, BOB, "pending")]


def test_deleted_caller_is_403(client, as_user, make_user):
    make_user(BOB, username="bob", deleted=True)
    response = _accept(client, as_user, BOB, ANNA)
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "account_deleted"
