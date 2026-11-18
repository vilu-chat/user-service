from conftest import ANNA, BOB


def test_me_stores_username_and_returns_it(client, as_user):
    body = client.get("/api/v1/users/me", headers=as_user(ANNA, preferred_username="  Anna ")).get_json()
    assert body["username"] == "anna"


def test_me_without_claim_has_null_username(client, as_user):
    body = client.get("/api/v1/users/me", headers=as_user(ANNA, preferred_username=None)).get_json()
    assert body["username"] is None


def test_patch_and_delete_also_sync(client, as_user, db_user):
    client.patch("/api/v1/users/me", json={"bio": "x"}, headers=as_user(ANNA, preferred_username="anna"))
    assert db_user(ANNA).username == "anna"
    client.delete("/api/v1/users/me", headers=as_user(BOB, preferred_username="bob"))
    assert db_user(BOB).username == "bob"


def test_taken_username_does_not_fail_the_request(client, as_user, db_user):
    client.get("/api/v1/users/me", headers=as_user(ANNA, preferred_username="shared"))
    response = client.get("/api/v1/users/me", headers=as_user(BOB, preferred_username="shared"))
    assert response.status_code == 200
    assert response.get_json()["username"] is None


def test_relation_endpoints_sync_too(client, as_user, db_user):
    client.get("/api/v1/users/me/relations", headers=as_user(ANNA, preferred_username="anna"))
    assert db_user(ANNA).username == "anna"
