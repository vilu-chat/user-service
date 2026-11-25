import uuid

from sqlalchemy import select

from app.extensions import db
from app.models import User


def get_by_id(user_id: uuid.UUID) -> User | None:
    return db.session.get(User, user_id)


def get_many_active(user_ids: list[uuid.UUID]) -> list[User]:
    """The users with these ids that exist and are not deleted."""
    return list(
        db.session.scalars(
            select(User).where(User.id.in_(user_ids), User.deleted_at.is_(None)).order_by(User.created_at, User.id)
        )
    )


def username_taken(username: str, exclude_id: uuid.UUID | None = None) -> bool:
    query = select(User.id).where(User.username == username)
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    return db.session.scalar(query.limit(1)) is not None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_by_username_prefix(prefix: str, exclude_id: uuid.UUID, limit: int) -> list[User]:
    """Active users whose username starts with `prefix` (already lowercase), ordered by username."""
    return list(
        db.session.scalars(
            select(User)
            .where(
                User.username.like(_escape_like(prefix) + "%", escape="\\"),
                User.id != exclude_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.username)
            .limit(limit)
        )
    )


def lock_pair(first_id: uuid.UUID, second_id: uuid.UUID) -> dict[uuid.UUID, User]:
    """SELECT ... FOR UPDATE on both rows in id order (same order for everyone, so no deadlock)."""
    rows = db.session.scalars(
        select(User).where(User.id.in_([first_id, second_id])).order_by(User.id).with_for_update()
    )
    return {user.id: user for user in rows}


def add(user: User) -> User:
    db.session.add(user)
    db.session.flush()
    return user
