from tests.conftest import ANNA, BOB

ME = "/api/v1/users/me"


def make_user(client, as_user, user=ANNA, name="Anna"):
    assert client.get(ME, headers=as_user(user, name=name)).status_code == 200


def assert_account_deleted(response):
    assert response.status_code == 403
    body = response.get_json()
    assert body["code"] == 403
    assert body["status"] == "Forbidden"
    assert body["error_code"] == "account_deleted"
    assert body["message"]


def test_delete_returns_204_and_soft_deletes(client, as_user, db_user):
    make_user(client, as_user)
    response = client.delete(ME, headers=as_user(ANNA))
    assert response.status_code == 204
    assert response.data == b""

    user = db_user(ANNA)
    assert user is not None  # soft delete: the row stays
    assert user.deleted_at is not None


def test_get_and_patch_me_return_403_account_deleted(client, as_user):
    make_user(client, as_user)
    client.delete(ME, headers=as_user(ANNA))
    assert_account_deleted(client.get(ME, headers=as_user(ANNA)))
    assert_account_deleted(client.patch(ME, json={"bio": "back?"}, headers=as_user(ANNA)))


def test_delete_writes_one_user_deleted_row(client, as_user, outbox):
    make_user(client, as_user)
    client.delete(ME, headers=as_user(ANNA))

    (event,) = outbox()
    assert event.event_type == "user.deleted"
    assert str(event.aggregate_id) == str(ANNA)
    assert event.payload == {"user_id": str(ANNA)}
    assert event.published_at is None


def test_second_delete_is_idempotent(client, as_user, db_user, outbox):
    make_user(client, as_user)
    client.delete(ME, headers=as_user(ANNA))
    first_deleted_at = db_user(ANNA).deleted_at

    again = client.delete(ME, headers=as_user(ANNA))
    assert again.status_code == 204
    assert db_user(ANNA).deleted_at == first_deleted_at  # unchanged
    assert len(outbox("user.deleted")) == 1  # no second event


def test_deleted_user_is_not_recreated_or_revived_by_lazy_provisioning(app, client, as_user, db_user):
    from sqlalchemy import func, select

    from app.extensions import db
    from app.models import User

    make_user(client, as_user, name="Anna")
    client.delete(ME, headers=as_user(ANNA))
    deleted_at = db_user(ANNA).deleted_at

    for _ in range(3):
        assert_account_deleted(client.get(ME, headers=as_user(ANNA, name="Anna Again")))
    assert_account_deleted(client.patch(ME, json={"display_name": "New"}, headers=as_user(ANNA)))

    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(User)) == 1
    user = db_user(ANNA)
    assert user.deleted_at == deleted_at
    assert user.display_name == "Anna"


def test_deleted_user_is_gone_from_get_by_id_and_lookup(client, as_user):
    make_user(client, as_user, BOB, "Bob")
    client.delete(ME, headers=as_user(BOB))
    assert client.get(f"/api/v1/users/{BOB}", headers=as_user(ANNA)).status_code == 404
    found = client.post("/api/v1/users/lookup", json={"ids": [str(BOB)]}, headers=as_user(ANNA))
    assert found.get_json() == []


def test_delete_without_a_profile_creates_a_deleted_row_that_stays_deleted(client, as_user, db_user, outbox):
    assert client.delete(ME, headers=as_user(ANNA)).status_code == 204
    assert db_user(ANNA).deleted_at is not None
    assert len(outbox("user.deleted")) == 1
    assert_account_deleted(client.get(ME, headers=as_user(ANNA)))


def test_delete_requires_auth(client):
    assert client.delete(ME).status_code == 401
