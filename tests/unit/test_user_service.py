import uuid

from app.services import user_service


def test_get_or_create_me_is_idempotent(app):
    user_id = uuid.uuid4()
    with app.app_context():
        first = user_service.get_or_create_me(user_id, "Bob Berg")
        second = user_service.get_or_create_me(user_id, "Ignored")
        assert first.id == second.id == user_id
        assert second.display_name == "Bob Berg"


def test_display_name_fallbacks_and_truncation(app):
    with app.app_context():
        assert user_service.get_or_create_me(uuid.uuid4(), None).display_name == "User"
        assert user_service.get_or_create_me(uuid.uuid4(), "   ").display_name == "User"
        assert user_service.get_or_create_me(uuid.uuid4(), 123).display_name == "User"
        assert len(user_service.get_or_create_me(uuid.uuid4(), "x" * 200).display_name) == 64
