import base64
import binascii
import json
import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.errors import ConflictError, InvalidRequestError, NotFoundError
from app.extensions import db
from app.models import User, UserRelation
from app.repositories import relation_repo, user_repo
from app.services import user_service


def _encode_cursor(created_at: datetime, other_user_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(other_user_id)])
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_at_text, id_text = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        created_at = datetime.fromisoformat(created_at_text)
        if created_at.tzinfo is None:
            raise ValueError("naive timestamp")
        return created_at, uuid.UUID(id_text)
    except (ValueError, TypeError, binascii.Error, UnicodeError):
        raise InvalidRequestError("Invalid cursor.") from None


def _item(relation: UserRelation, other: User, direction: str | None) -> dict:
    return {
        "other_user_id": other.id,  # for incoming rows this is the sender, not relation.other_user_id
        "kind": relation.kind,
        "direction": direction,
        "created_at": relation.created_at,
        "user": other,
    }


def _lock(caller_id: uuid.UUID, other_user_id: uuid.UUID) -> User:
    """Lock both users rows (ordered by id) and return the other, active user or raise 404.

    Two requests that touch the same pair queue up here, so opposite requests cannot both succeed.
    """
    locked = user_repo.lock_pair(caller_id, other_user_id)
    other = locked.get(other_user_id)
    if other is None or other.deleted_at is not None:
        db.session.rollback()
        raise NotFoundError("User not found.")
    return other


def list_mine(
    user_id: uuid.UUID,
    username_claim,
    name_claim,
    kind: str = "contact",
    direction: str = "incoming",
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    user_service.get_or_create_me(user_id, name_claim, username_claim)
    after = _decode_cursor(cursor) if cursor else None
    incoming = kind == "pending" and direction == "incoming"
    rows = relation_repo.list_page(user_id, kind, incoming, limit + 1, after)
    has_more = len(rows) > limit
    rows = rows[:limit]

    if kind == "contact":
        shown_direction = None
    else:
        shown_direction = "incoming" if incoming else "outgoing"
    items = [_item(relation, other, shown_direction) for relation, other in rows]
    last = rows[-1] if has_more else None
    return {
        "items": items,
        "next_cursor": _encode_cursor(last[0].created_at, last[1].id) if last else None,
    }


def send(user_id: uuid.UUID, other_user_id: uuid.UUID, name_claim=None, username_claim=None) -> dict:
    user_service.get_or_create_me(user_id, name_claim, username_claim)
    if other_user_id == user_id:
        raise InvalidRequestError("You cannot send a request to yourself.")
    other = _lock(user_id, other_user_id)

    existing = relation_repo.get(user_id, other_user_id)
    if existing is not None and existing.kind == "contact":
        raise _conflict("You are already contacts.")
    if existing is not None and existing.kind == "pending":
        raise _conflict("You have already sent a request to this user.")
    reverse = relation_repo.get(other_user_id, user_id)
    if reverse is not None and reverse.kind in ("pending", "contact"):
        raise _conflict("This user has already sent you a request.")

    try:
        relation = relation_repo.add(UserRelation(user_id=user_id, other_user_id=other_user_id, kind="pending"))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise _conflict("A relation with this user already exists.") from None
    return _item(relation, other, "outgoing")


def _conflict(message: str) -> ConflictError:
    db.session.rollback()  # release the row locks before answering
    return ConflictError(message)


def accept(user_id: uuid.UUID, other_user_id: uuid.UUID, name_claim=None, username_claim=None) -> dict:
    user_service.get_or_create_me(user_id, name_claim, username_claim)
    if other_user_id == user_id:
        raise NotFoundError("No request from this user.")
    other = _lock(user_id, other_user_id)

    own = relation_repo.get(user_id, other_user_id)
    if own is not None and own.kind == "contact":
        db.session.rollback()
        return _item(own, other, None)  # already contacts: nothing changes

    incoming = relation_repo.get(other_user_id, user_id)
    if incoming is None or incoming.kind != "pending":
        db.session.rollback()
        raise NotFoundError("No request from this user.")

    incoming.kind = "contact"
    if own is not None:  # a stray row of the caller's own, replaced by the contact row
        own.kind = "contact"
    else:
        own = relation_repo.add(UserRelation(user_id=user_id, other_user_id=other_user_id, kind="contact"))
    db.session.commit()
    return _item(own, other, None)


def remove(user_id: uuid.UUID, other_user_id: uuid.UUID, name_claim=None, username_claim=None) -> None:
    """Remove a contact, cancel an own request or decline a received one. Always succeeds."""
    user_service.get_or_create_me(user_id, name_claim, username_claim)
    if other_user_id == user_id:
        return
    locked = user_repo.lock_pair(user_id, other_user_id)
    if other_user_id in locked:
        relation_repo.delete_between(user_id, other_user_id)
    db.session.commit()
