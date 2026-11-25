from conftest import ANNA, BOB, CECILIA


def _delete(client, as_user, caller, other):
    return client.delete(f"/api/v1/users/me/relations/{other}", headers=as_user(caller))


def test_remove_contact_removes_both_rows(client, as_user, make_user, make_relation, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    make_user(CECILIA, username="cecilia")
    make_relation(ANNA, BOB, "contact")
    make_relation(BOB, ANNA, "contact")
    make_relation(ANNA, CECILIA, "contact")
    make_relation(CECILIA, ANNA, "contact")
    assert _delete(client, as_user, ANNA, BOB).status_code == 204
    assert relation_rows() == sorted([(ANNA, CECILIA, "contact"), (CECILIA, ANNA, "contact")])


def test_cancel_own_request(client, as_user, make_user, make_relation, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    make_relation(ANNA, BOB, "pending")
    assert _delete(client, as_user, ANNA, BOB).status_code == 204
    assert relation_rows() == []


def test_decline_received_request(client, as_user, make_user, make_relation, relation_rows):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob")
    make_relation(ANNA, BOB, "pending")
    assert _delete(client, as_user, BOB, ANNA).status_code == 204
    assert relation_rows() == []


def test_idempotent_204(client, as_user, make_user):
    make_user(BOB, username="bob")
    assert _delete(client, as_user, ANNA, BOB).status_code == 204
    assert _delete(client, as_user, ANNA, BOB).status_code == 204
    import uuid

    assert _delete(client, as_user, ANNA, uuid.uuid4()).status_code == 204
    assert _delete(client, as_user, ANNA, ANNA).status_code == 204


def test_deleted_caller_is_403(client, as_user, make_user):
    make_user(ANNA, username="anna", deleted=True)
    response = _delete(client, as_user, ANNA, BOB)
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "account_deleted"
