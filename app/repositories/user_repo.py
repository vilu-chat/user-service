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


def add(user: User) -> User:
    db.session.add(user)
    db.session.flush()
    return user
