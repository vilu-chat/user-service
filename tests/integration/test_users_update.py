import pytest

from tests.conftest import ANNA

URL = "/api/v1/users/me"


def patch(client, as_user, body, user=ANNA, **claims):
    return client.patch(URL, json=body, headers=as_user(user, **claims))


def test_patch_applies_only_the_fields_that_were_sent(client, as_user):
    patch(client, as_user, {"display_name": "Anna", "bio": "Hello", "locale": "sv", "timezone": "Europe/Stockholm"})

    response = patch(client, as_user, {"status_text": "busy"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["status_text"] == "busy"
    assert (body["display_name"], body["bio"], body["locale"], body["timezone"]) == (
        "Anna",
        "Hello",
        "sv",
        "Europe/Stockholm",
    )

    # and it persisted
    again = client.get(URL, headers=as_user(ANNA)).get_json()
    assert again == body


def test_patch_can_clear_nullable_fields_but_not_display_name(client, as_user):
    patch(client, as_user, {"bio": "x", "status_text": "y", "locale": "sv", "timezone": "UTC"})
    cleared = patch(client, as_user, {"bio": None, "status_text": None, "locale": None, "timezone": None})
    body = cleared.get_json()
    assert (body["bio"], body["status_text"], body["locale"], body["timezone"]) == (None, None, None, None)
    assert patch(client, as_user, {"display_name": None}).status_code == 422


def test_display_name_is_trimmed(client, as_user):
    response = patch(client, as_user, {"display_name": "   Anna B   "})
    assert response.status_code == 200
    assert response.get_json()["display_name"] == "Anna B"


@pytest.mark.parametrize("value", ["", " ", "\t\n ", "x" * 65, 123])
def test_invalid_display_name_is_rejected_and_nothing_changes(client, as_user, value):
    client.get(URL, headers=as_user(ANNA, name="Original"))
    response = patch(client, as_user, {"display_name": value})
    assert response.status_code == 422
    assert client.get(URL, headers=as_user(ANNA)).get_json()["display_name"] == "Original"


def test_padding_does_not_count_towards_max_length(client, as_user):
    assert patch(client, as_user, {"display_name": "  " + "x" * 64 + "  "}).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"bio": "x" * 501},
        {"status_text": "x" * 141},
        {"locale": "x" * 11},
        {"timezone": "x" * 65},
        {"id": "0b1f6a4e-5c1d-4e8a-9a57-3f2d8c1a0002"},
        {"avatar_key": "a/b.png"},
        {"avatar_version": 5},
        {"created_at": "2020-01-01T00:00:00Z"},
        {"deleted_at": None},
        {"avatar_url": "http://x"},
    ],
)
def test_invalid_or_read_only_fields_are_rejected(client, as_user, body):
    assert patch(client, as_user, body).status_code == 422


def test_empty_patch_changes_nothing(client, as_user, outbox):
    before = client.get(URL, headers=as_user(ANNA, name="Anna")).get_json()
    response = patch(client, as_user, {})
    assert response.status_code == 200
    assert response.get_json() == before
    assert outbox() == []


def test_patch_before_any_get_provisions_the_row(client, as_user):
    response = patch(client, as_user, {"bio": "first"}, name="Anna Andersson")
    assert response.status_code == 200
    assert response.get_json()["display_name"] == "Anna Andersson"
    assert response.get_json()["bio"] == "first"


def test_response_has_avatar_url_null(client, as_user):
    body = patch(client, as_user, {"bio": "x"}).get_json()
    assert "avatar_url" in body and body["avatar_url"] is None


# --- outbox: user.updated only when display_name actually changes


def test_display_name_change_writes_one_user_updated_row(client, as_user, outbox):
    client.get(URL, headers=as_user(ANNA, name="Old Name"))
    patch(client, as_user, {"display_name": "  New Name "})

    (event,) = outbox()
    assert event.event_type == "user.updated"
    assert str(event.aggregate_id) == str(ANNA)
    assert event.payload == {"user_id": str(ANNA), "display_name": "New Name"}
    assert event.published_at is None


def test_no_outbox_row_when_display_name_is_unchanged(client, as_user, outbox):
    client.get(URL, headers=as_user(ANNA, name="Same"))
    patch(client, as_user, {"display_name": "Same"})
    patch(client, as_user, {"display_name": "  Same  "})  # equal after trimming
    assert outbox() == []


def test_no_outbox_row_when_other_fields_change(client, as_user, outbox):
    patch(client, as_user, {"bio": "b", "status_text": "s", "locale": "sv", "timezone": "UTC"})
    assert outbox() == []


def test_mixed_patch_writes_one_row_per_actual_name_change(client, as_user, outbox):
    client.get(URL, headers=as_user(ANNA, name="A"))
    patch(client, as_user, {"display_name": "B", "bio": "x"})
    patch(client, as_user, {"display_name": "B", "bio": "y"})  # same name again
    patch(client, as_user, {"display_name": "C"})
    assert [e.payload["display_name"] for e in outbox("user.updated")] == ["B", "C"]


def test_failed_patch_writes_no_outbox_row(client, as_user, outbox):
    client.get(URL, headers=as_user(ANNA, name="A"))
    patch(client, as_user, {"display_name": "B", "bio": "x" * 501})
    assert outbox() == []
