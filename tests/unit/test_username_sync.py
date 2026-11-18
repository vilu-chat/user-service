import logging
import uuid

from app.extensions import db
from app.models import User
from app.services import user_service


def _username(user_id):
    return db.session.get(User, user_id).username


def test_normalise_username():
    assert user_service.normalise_username("  Anna ") == "anna"
    assert user_service.normalise_username("   ") is None
    assert user_service.normalise_username("") is None
    assert user_service.normalise_username(None) is None
    assert user_service.normalise_username(42) is None


def test_stored_on_first_call_trimmed_and_lowercased(app):
    user_id = uuid.uuid4()
    with app.app_context():
        user_service.get_or_create_me(user_id, "Anna", "  AnNa ")
        assert _username(user_id) == "anna"


def test_filled_in_for_existing_row_with_null(app, make_user):
    user_id = make_user(uuid.uuid4())
    with app.app_context():
        assert _username(user_id) is None
        user_service.get_or_create_me(user_id, "Anna", "anna")
        assert _username(user_id) == "anna"


def test_updated_when_it_changes(app):
    user_id = uuid.uuid4()
    with app.app_context():
        user_service.get_or_create_me(user_id, "Anna", "anna")
        user_service.get_or_create_me(user_id, "Anna", "anna2")
        assert _username(user_id) == "anna2"


def test_ignored_when_taken_by_someone_else(app, make_user, caplog):
    make_user(uuid.uuid4(), username="anna")
    user_id = make_user(uuid.uuid4(), username="old")
    # Alembic's fileConfig (run by the migration fixture) disables loggers that already exist.
    user_service.logger.disabled = False
    with app.app_context(), caplog.at_level(logging.WARNING):
        user_service.get_or_create_me(user_id, "Other", "anna")  # does not raise
        assert _username(user_id) == "old"
    assert "taken" in caplog.text


def test_new_row_is_created_without_username_when_taken(app, make_user):
    make_user(uuid.uuid4(), username="anna")
    user_id = uuid.uuid4()
    with app.app_context():
        user_service.get_or_create_me(user_id, "Other", "anna")
        assert _username(user_id) is None


def test_missing_or_blank_claim_changes_nothing(app):
    user_id = uuid.uuid4()
    with app.app_context():
        user_service.get_or_create_me(user_id, "Anna", "anna")
        user_service.get_or_create_me(user_id, "Anna", None)
        user_service.get_or_create_me(user_id, "Anna", "  ")
        assert _username(user_id) == "anna"
        assert _username(user_service.get_or_create_me(uuid.uuid4(), "Bob", None).id) is None


def test_deleted_rows_are_not_updated(app):
    user_id = uuid.uuid4()
    with app.app_context():
        user_service.get_or_create_me(user_id, "Anna", "anna")
        user_service.delete_me(user_id, "Anna", "anna")
        user = db.session.get(User, user_id)
        assert user_service.sync_username(user, "changed") is False
        assert _username(user_id) == "anna"


def test_username_change_publishes_no_event(app, outbox):
    user_id = uuid.uuid4()
    with app.app_context():
        user_service.get_or_create_me(user_id, "Anna", "anna")
        user_service.get_or_create_me(user_id, "Anna", "anna2")
    assert outbox() == []
