import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.errors import AccountDeletedError, NotFoundError
from app.extensions import db
from app.models import OutboxEvent, User
from app.repositories import outbox_repo, user_repo
from app.schemas import UserDeletedDataSchema, UserUpdatedDataSchema

logger = logging.getLogger(__name__)

DEFAULT_DISPLAY_NAME = "User"
DISPLAY_NAME_MAX = 64


def _display_name_from_claim(name) -> str:
    if isinstance(name, str) and name.strip():
        return name.strip()[:DISPLAY_NAME_MAX]
    return DEFAULT_DISPLAY_NAME


def normalise_username(claim) -> str | None:
    """The token's preferred_username, trimmed and lowercased; None when missing or blank."""
    if isinstance(claim, str) and claim.strip():
        return claim.strip().lower()
    return None


def sync_username(user: User, username_claim) -> bool:
    """Copy the token's username onto an existing, non-deleted row. Returns True if the row changed.

    The one shared helper for every /me and relation endpoint. It never raises: if another user
    already has the username, the old value stays and a warning is logged. The caller commits.
    No user.updated event is written for username changes.
    """
    username = normalise_username(username_claim)
    if username is None or user.deleted_at is not None or user.username == username:
        return False
    try:
        if user_repo.username_taken(username, exclude_id=user.id):
            logger.warning("Username %r of user %s is taken by another user; keeping %r", username, user.id, user.username)
            return False
        with db.session.begin_nested():  # a savepoint, so a lost race does not poison the request
            user.username = username
            db.session.flush()
        return True
    except SQLAlchemyError:
        logger.warning("Could not store username %r for user %s", username, user.id, exc_info=True)
        db.session.refresh(user)
        return False


def _new_user(user_id: uuid.UUID, name_claim, username: str | None) -> User:
    return user_repo.add(User(id=user_id, display_name=_display_name_from_claim(name_claim), username=username))


def _provision(user_id: uuid.UUID, name_claim, username_claim=None) -> User:
    """The caller's row, created on first use. Returns deleted rows too; it never revives them."""
    user = user_repo.get_by_id(user_id)
    if user is not None:
        return user

    username = normalise_username(username_claim)
    if username is not None and user_repo.username_taken(username):
        logger.warning("Username %r is taken by another user; creating %s without a username", username, user_id)
        username = None

    try:
        user = _new_user(user_id, name_claim, username)
        db.session.commit()
    except IntegrityError:
        # A concurrent first request created the row (or took the username) between our read and insert.
        db.session.rollback()
        user = user_repo.get_by_id(user_id)
        if user is None:
            user = _new_user(user_id, name_claim, None)
            db.session.commit()
    return user


def get_or_create_me(user_id: uuid.UUID, name_claim=None, username_claim=None) -> User:
    """Lazy provisioning: the first authenticated call creates the user row."""
    user = _provision(user_id, name_claim, username_claim)
    if user.deleted_at is not None:
        raise AccountDeletedError()
    if sync_username(user, username_claim):
        db.session.commit()
    return user


def update_me(user_id: uuid.UUID, name_claim, data: dict, username_claim=None) -> User:
    """Apply only the fields present in `data`. Writes user.updated when display_name changes."""
    user = get_or_create_me(user_id, name_claim, username_claim)

    display_name_changed = "display_name" in data and data["display_name"] != user.display_name
    for field, value in data.items():
        setattr(user, field, value)

    if display_name_changed:
        payload = UserUpdatedDataSchema().dump({"user_id": user.id, "display_name": user.display_name})
        outbox_repo.add(OutboxEvent(aggregate_id=user.id, event_type="user.updated", payload=payload))
    db.session.commit()
    return user


def delete_me(user_id: uuid.UUID, name_claim=None, username_claim=None) -> None:
    """Soft delete. Idempotent: deleting an already deleted account changes nothing."""
    # A caller who never used the service gets a row first, so the deletion sticks and
    # lazy provisioning cannot create a fresh profile for them later.
    user = _provision(user_id, name_claim, username_claim)
    if user.deleted_at is not None:
        return
    sync_username(user, username_claim)

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


def search(caller_id: uuid.UUID, q: str, limit: int) -> list[User]:
    """Users whose username starts with q (trimmed, lowercased). Leaves out the caller and deleted users."""
    return user_repo.search_by_username_prefix(q.strip().lower(), caller_id, limit)
