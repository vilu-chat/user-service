from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from conftest import ANNA, BOB, CECILIA, DAVID
import uuid

URL = "/api/v1/users/me/relations"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _get(client, as_user, caller=ANNA, **params):
    return client.get(URL, query_string=params, headers=as_user(caller))


def _ids(response):
    return [item["other_user_id"] for item in response.get_json()["items"]]


def _users(make_user):
    for user_id, name in ((ANNA, "anna"), (BOB, "bob"), (CECILIA, "cecilia"), (DAVID, "david")):
        make_user(user_id, username=name)


def test_empty_for_new_caller(client, as_user):
    response = _get(client, as_user)
    assert response.status_code == 200
    assert response.get_json() == {"items": [], "next_cursor": None}


def test_contacts_newest_first_with_nested_profile(client, as_user, make_user, make_relation):
    _users(make_user)
    make_relation(ANNA, BOB, "contact", T0)
    make_relation(ANNA, CECILIA, "contact", T0 + timedelta(minutes=1))
    make_relation(BOB, ANNA, "contact", T0)
    make_relation(ANNA, DAVID, "pending", T0 + timedelta(minutes=2))  # not a contact
    body = _get(client, as_user).get_json()
    assert [i["other_user_id"] for i in body["items"]] == [str(CECILIA), str(BOB)]
    item = body["items"][0]
    assert item["kind"] == "contact"
    assert item["direction"] is None
    assert item["created_at"]
    assert item["user"]["id"] == str(CECILIA)
    assert item["user"]["username"] == "cecilia"
    assert set(item["user"]) == {"id", "username", "display_name", "bio", "status_text", "avatar_url"}


def test_incoming_pending(client, as_user, make_user, make_relation):
    _users(make_user)
    make_relation(BOB, ANNA, "pending", T0)
    make_relation(CECILIA, ANNA, "pending", T0 + timedelta(minutes=1))
    make_relation(ANNA, DAVID, "pending", T0)  # outgoing, not listed
    for params in ({"kind": "pending"}, {"kind": "pending", "direction": "incoming"}):
        body = _get(client, as_user, **params).get_json()
        assert [i["other_user_id"] for i in body["items"]] == [str(CECILIA), str(BOB)]
        assert {i["direction"] for i in body["items"]} == {"incoming"}
        assert body["items"][0]["user"]["username"] == "cecilia"  # the sender's profile


def test_outgoing_pending(client, as_user, make_user, make_relation):
    _users(make_user)
    make_relation(ANNA, BOB, "pending", T0)
    make_relation(ANNA, CECILIA, "pending", T0 + timedelta(minutes=1))
    make_relation(DAVID, ANNA, "pending", T0)  # incoming, not listed
    body = _get(client, as_user, kind="pending", direction="outgoing").get_json()
    assert [i["other_user_id"] for i in body["items"]] == [str(CECILIA), str(BOB)]
    assert {i["direction"] for i in body["items"]} == {"outgoing"}


def test_direction_is_ignored_for_contacts(client, as_user, make_user, make_relation):
    _users(make_user)
    make_relation(ANNA, BOB, "contact")
    assert _ids(_get(client, as_user, direction="outgoing")) == [str(BOB)]


def test_pagination_across_pages_including_equal_timestamps(client, as_user, make_user, make_relation):
    make_user(ANNA, username="anna")
    others = [uuid.UUID(int=i + 1) for i in range(7)]
    for i, other in enumerate(others):
        make_user(other, username=f"u{i}")
        # Three rows share a timestamp, so the tiebreaker matters.
        make_relation(ANNA, other, "contact", T0 + timedelta(minutes=i // 3))

    seen, cursor, pages = [], None, 0
    while True:
        params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        body = _get(client, as_user, **params).get_json()
        seen += [i["other_user_id"] for i in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert pages == 3
    assert len(seen) == 7 and len(set(seen)) == 7
    assert seen == [str(o) for o in sorted(others, key=lambda o: (others.index(o) // 3, o), reverse=True)]


def test_exact_page_has_no_next_cursor(client, as_user, make_user, make_relation):
    _users(make_user)
    make_relation(ANNA, BOB, "contact")
    make_relation(ANNA, CECILIA, "contact")
    assert _get(client, as_user, limit=2).get_json()["next_cursor"] is None


def test_deleted_users_are_hidden(client, as_user, make_user, make_relation):
    make_user(ANNA, username="anna")
    make_user(BOB, username="bob", deleted=True)
    make_user(CECILIA, username="cecilia")
    make_relation(ANNA, BOB, "contact")
    make_relation(ANNA, CECILIA, "contact")
    make_relation(BOB, ANNA, "pending")
    assert _ids(_get(client, as_user)) == [str(CECILIA)]
    assert _ids(_get(client, as_user, kind="pending")) == []


def test_validation(client, as_user):
    assert _get(client, as_user, kind="blocked").status_code == 422
    assert _get(client, as_user, direction="sideways").status_code == 422
    assert _get(client, as_user, limit=0).status_code == 422
    assert _get(client, as_user, limit=101).status_code == 422
    assert _get(client, as_user, cursor="garbage").status_code == 400
    assert client.get(URL).status_code == 401


def test_deleted_caller_is_403(client, as_user, make_user):
    make_user(ANNA, username="anna", deleted=True)
    response = _get(client, as_user)
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "account_deleted"


def test_no_n_plus_one(app, client, as_user, make_user, make_relation):
    make_user(ANNA, username="anna")
    for i in range(10):
        other = uuid.UUID(int=i + 1)
        make_user(other, username=f"u{i}")
        make_relation(ANNA, other, "contact", T0 + timedelta(minutes=i))
    _get(client, as_user)  # warm up (provisioning etc.)

    statements = []

    def count(conn, cursor, statement, *args):
        statements.append(statement)

    from app.extensions import db

    with app.app_context():
        engine = db.engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        assert len(_get(client, as_user, limit=10).get_json()["items"]) == 10
        few = len(statements)
        statements.clear()
        assert len(_get(client, as_user, limit=2).get_json()["items"]) == 2
        fewer = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert few == fewer  # the query count does not grow with the number of items
    assert sum("user_relations" in s for s in statements) == 1  # one query for the page, users joined in
