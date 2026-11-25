from conftest import ANNA, BOB, CECILIA, DAVID
import uuid

URL = "/api/v1/users/search"


def _search(client, as_user, q, caller=ANNA, **params):
    return client.get(URL, query_string={"q": q, **params}, headers=as_user(caller))


def _names(response):
    return [u["username"] for u in response.get_json()]


def test_prefix_match_ordered_by_username(client, as_user, make_user):
    for name in ("bobby", "bob", "bobcat", "joanbob"):
        make_user(uuid.uuid4(), username=name)
    response = _search(client, as_user, "bob")
    assert response.status_code == 200
    assert _names(response) == ["bob", "bobby", "bobcat"]
    assert set(response.get_json()[0]) == {"id", "username", "display_name", "bio", "status_text", "avatar_url"}


def test_case_insensitive_and_trimmed(client, as_user, make_user):
    make_user(BOB, username="bob")
    assert _names(_search(client, as_user, "  BOB ")) == ["bob"]


def test_min_and_max_length(client, as_user):
    assert _search(client, as_user, "ab").status_code == 422
    assert _search(client, as_user, "  ab  ").status_code == 422
    assert _search(client, as_user, "").status_code == 422
    assert _search(client, as_user, "a" * 65).status_code == 422
    assert client.get(URL, headers=as_user(ANNA)).status_code == 422
    assert _search(client, as_user, "a" * 64).status_code == 200


def test_wildcards_are_escaped(client, as_user, make_user):
    make_user(uuid.uuid4(), username="a_cde")
    make_user(uuid.uuid4(), username="abcde")
    make_user(uuid.uuid4(), username="100%pure")
    make_user(uuid.uuid4(), username="100xpure")
    make_user(uuid.uuid4(), username="back\\slash")
    assert _names(_search(client, as_user, "a_c")) == ["a_cde"]
    assert _names(_search(client, as_user, "100%")) == ["100%pure"]
    assert _names(_search(client, as_user, "back\\")) == ["back\\slash"]
    assert _names(_search(client, as_user, "%%%")) == []


def test_excludes_self_deleted_and_null_username(client, as_user, make_user):
    make_user(ANNA, username="anna")
    make_user(BOB, username="annabel")
    make_user(CECILIA, username="annette", deleted=True)
    make_user(DAVID, username=None)
    assert _names(_search(client, as_user, "ann")) == ["annabel"]


def test_limit(client, as_user, make_user):
    for i in range(25):
        make_user(uuid.uuid4(), username=f"user{i:02d}")
    assert len(_search(client, as_user, "user").get_json()) == 20
    assert len(_search(client, as_user, "user", limit=3).get_json()) == 3
    assert _search(client, as_user, "user", limit=21).status_code == 422
    assert _search(client, as_user, "user", limit=0).status_code == 422


def test_requires_auth_and_does_not_clash_with_user_id(client, as_user, make_user):
    assert client.get(URL, query_string={"q": "abc"}).status_code == 401
    make_user(BOB, username="bob")
    assert client.get(f"/api/v1/users/{BOB}", headers=as_user(ANNA)).status_code == 200
