from app.extensions import db
from app.models import OutboxEvent


def add(event: OutboxEvent) -> OutboxEvent:
    db.session.add(event)
    db.session.flush()
    return event
