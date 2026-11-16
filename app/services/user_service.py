import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.errors import AccountDeletedError, NotFoundError
from app.extensions import db
from app.models import OutboxEvent, User
from app.repositories import outbox_repo, user_repo
from app.schemas import UserDeletedDataSchema, UserUpdatedDataSchema

DEFAULT_DISPLAY_NAME = "User"
DISPLAY_NAME_MAX = 64


def _display_name_from_claim(name) -> str:
    if isinstance(name, str) and name.strip():
        return name.strip()[:DISPLAY_NAME_MAX]
    return DEFAULT_DISPLAY_NAME


def _provision(user_id: uuid.UUID, name_claim) -> User:
    """The caller's row, created on first use. Returns deleted rows too; it never revives them."""
    user = user_repo.get_by_id(user_id)
    if user is not None:
        return user

    try:
        user = user_repo.add(User(id=user_id, display_name=_display_name_from_claim(name_claim)))
        db.session.commit()
    except IntegrityError:
        # A concurrent first request created the row between our read and insert.
        db.session.rollback()
        user = user_repo.get_by_id(user_id)
    return user


def get_or_create_me(user_id: uuid.UUID, name_claim=None) -> User:
    """Lazy provisioning: the first authenticated call creates the user row."""
    user = _provision(user_id, name_claim)
    if user.deleted_at is not None:
        raise AccountDeletedError()
    return user


def update_me(user_id: uuid.UUID, name_claim, data: dict) -> User:
    """Apply only the fields present in `data`. Writes user.updated when display_name changes."""
    user = get_or_create_me(user_id, name_claim)

    display_name_changed = "display_name" in data and data["display_name"] != user.display_name
    for field, value in data.items():
        setattr(user, field, value)

    if display_name_changed:
        payload = UserUpdatedDataSchema().dump({"user_id": user.id, "display_name": user.display_name})
        outbox_repo.add(OutboxEvent(aggregate_id=user.id, event_type="user.updated", payload=payload))
    db.session.commit()
    return user


def delete_me(user_id: uuid.UUID, name_claim=None) -> None:
    """Soft delete. Idempotent: deleting an already deleted account changes nothing."""
    # A caller who never used the service gets a row first, so the deletion sticks and
    # lazy provisioning cannot create a fresh profile for them later.
    user = _provision(user_id, name_claim)
    if user.deleted_at is not None:
        return

    user.deleted_at = datetime.now(timezone.utc)
    payload = UserDeletedDataSchema().dump({"user_id": user.id})
    outbox_repo.add(OutboxEvent(aggregate_id=user.id, event_type="user.deleted", payload=payload))
    db.session.commit()


def get_public(user_id: uuid.UUID) -> User:
    user = user_repo.get_by_id(user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User not found.")
    return user


def lookup(user_ids: list[uuid.UUID]) -> list[User]:
    """Found, non-deleted users; unknown and deleted ids are silently omitted."""
    return user_repo.get_many_active(list(dict.fromkeys(user_ids)))
