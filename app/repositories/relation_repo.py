import uuid
from datetime import datetime

from sqlalchemy import delete, or_, select, tuple_

from app.extensions import db
from app.models import User, UserRelation


def get(user_id: uuid.UUID, other_user_id: uuid.UUID) -> UserRelation | None:
    return db.session.get(UserRelation, (user_id, other_user_id))


def add(relation: UserRelation) -> UserRelation:
    db.session.add(relation)
    db.session.flush()
    return relation


def delete_between(first_id: uuid.UUID, second_id: uuid.UUID) -> None:
    """Every contact or pending row between the two users, in both directions."""
    db.session.execute(
        delete(UserRelation).where(
            UserRelation.kind.in_(["contact", "pending"]),
            or_(
                (UserRelation.user_id == first_id) & (UserRelation.other_user_id == second_id),
                (UserRelation.user_id == second_id) & (UserRelation.other_user_id == first_id),
            ),
        )
    )


def list_page(
    user_id: uuid.UUID,
    kind: str,
    incoming: bool,
    limit: int,
    after: tuple[datetime, uuid.UUID] | None = None,
) -> list[tuple[UserRelation, User]]:
    """Relations of `kind` with the other user's row joined in (one query, no N+1).

    Outgoing rows and contacts are rows where user_id is the caller; incoming ones are rows where
    other_user_id is the caller (ix_user_relations_other_user_id). The "other" user is the one on
    the opposite side. Newest first, ordered by (created_at, other user id) descending; `after` is
    that pair for the last item of the previous page. Rows whose other user is deleted are left out.
    """
    if incoming:
        query = select(UserRelation, User).join(User, User.id == UserRelation.user_id)
        query = query.where(UserRelation.other_user_id == user_id)
    else:
        query = select(UserRelation, User).join(User, User.id == UserRelation.other_user_id)
        query = query.where(UserRelation.user_id == user_id)
    query = query.where(UserRelation.kind == kind, User.deleted_at.is_(None))
    if after is not None:
        query = query.where(tuple_(UserRelation.created_at, User.id) < tuple_(*after))
    rows = db.session.execute(query.order_by(UserRelation.created_at.desc(), User.id.desc()).limit(limit))
    return [(relation, other) for relation, other in rows]
