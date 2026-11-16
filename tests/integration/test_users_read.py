import uuid

from tests.conftest import ANNA, BOB, CECILIA

PUBLIC_FIELDS = {"id", "display_name", "bio", "status_text", "avatar_url"}


def provision(client, as_user, user, name):
    assert client.get("/api/v1/users/me", headers=as_user(user, name=name)).status_code == 200


def delete(client, as_user, user):
    assert client.delete("/api/v1/users/me", headers=as_user(user)).status_code == 204


# --- GET /users/{id}


def test_get_user_by_id_returns_public_profile_only(client, as_user):
    provision(client, as_user, BOB, "Bob Berg")
    client.patch("/api/v1/users/me", json={"bio": "hi", "locale": "sv"}, headers=as_user(BOB))

    response = client.get(f"/api/v1/users/{BOB}", headers=as_user(ANNA))
    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == PUBLIC_FIELDS
    assert body["id"] == str(BOB)
    assert body["display_name"] == "Bob Berg"
    assert body["bio"] == "hi"
    assert body["avatar_url"] is None


def test_get_user_by_id_missing_is_404(client, as_user):
    response = client.get(f"/api/v1/users/{uuid.uuid4()}", headers=as_user(ANNA))
    assert response.status_code == 404
    assert response.get_json()["status"] == "Not Found"


def test_get_user_by_id_deleted_is_404_with_same_body_as_missing(client, as_user):
    provision(client, as_user, BOB, "Bob")
    delete(client, as_user, BOB)
    deleted = client.get(f"/api/v1/users/{BOB}", headers=as_user(ANNA))
    missing = client.get(f"/api/v1/users/{uuid.uuid4()}", headers=as_user(ANNA))
    assert deleted.status_code == missing.status_code == 404
    assert deleted.get_json() == missing.get_json()  # a deleted account is indistinguishable from none


def test_get_user_by_id_requires_auth(client):
    assert client.get(f"/api/v1/users/{BOB}").status_code == 401


def test_get_user_by_id_with_invalid_uuid_is_404(client, as_user):
    assert client.get("/api/v1/users/not-a-uuid", headers=as_user(ANNA)).status_code == 404


# --- POST /users/lookup


def lookup(client, as_user, ids, user=ANNA):
    return client.post("/api/v1/users/lookup", json={"ids": [str(i) for i in ids]}, headers=as_user(user))


def test_lookup_returns_found_and_omits_missing_and_deleted(client, as_user):
    provision(client, as_user, BOB, "Bob")
    provision(client, as_user, CECILIA, "Cecilia")
    delete(client, as_user, CECILIA)

    response = lookup(client, as_user, [BOB, CECILIA, uuid.uuid4()])
    assert response.status_code == 200
    body = response.get_json()
    assert [u["id"] for u in body] == [str(BOB)]
    assert set(body[0]) == PUBLIC_FIELDS


def test_lookup_with_only_unknown_ids_returns_empty_list(client, as_user):
    assert lookup(client, as_user, [uuid.uuid4(), uuid.uuid4()]).get_json() == []


def test_lookup_ignores_duplicate_ids(client, as_user):
    provision(client, as_user, BOB, "Bob")
    assert len(lookup(client, as_user, [BOB, BOB, BOB]).get_json()) == 1


def test_lookup_accepts_exactly_100_ids_and_rejects_101(client, as_user):
    assert lookup(client, as_user, [uuid.uuid4() for _ in range(100)]).status_code == 200
    assert lookup(client, as_user, [uuid.uuid4() for _ in range(101)]).status_code == 422


def test_lookup_validation(client, as_user):
    assert lookup(client, as_user, []).status_code == 422
    assert client.post("/api/v1/users/lookup", json={}, headers=as_user(ANNA)).status_code == 422
    assert client.post("/api/v1/users/lookup", json={"ids": ["nope"]}, headers=as_user(ANNA)).status_code == 422


def test_lookup_requires_auth(client):
    assert client.post("/api/v1/users/lookup", json={"ids": []}).status_code == 401


def test_lookup_does_not_provision_anyone(client, as_user, db_user):
    lookup(client, as_user, [BOB])
    assert db_user(BOB) is None
    assert db_user(ANNA) is None
