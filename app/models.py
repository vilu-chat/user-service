from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Uuid, primary_key=True)  # Keycloak sub, no default
    display_name = db.Column(db.String(64), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    status_text = db.Column(db.String(140), nullable=True)
    avatar_key = db.Column(db.String(255), nullable=True)
    avatar_version = db.Column(
        db.Integer, default=0, server_default="0", nullable=False
    )
    locale = db.Column(db.String(10), nullable=True)
    timezone = db.Column(db.String(64), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)


class OutboxEvent(db.Model):  # same shape in both services
    __tablename__ = "outbox_events"
    __table_args__ = (
        # Partial index for the relay: only rows that still have to be published.
        db.Index("ix_outbox_unpublished", "id", postgresql_where=db.text("published_at IS NULL")),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    aggregate_id = db.Column(db.Uuid, nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(JSONB, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
