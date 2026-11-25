"""create outbox events table

Reviewed by hand against design.md, "User Service: database".

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-16 18:31:48.605293

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('outbox_events',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('aggregate_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events'))
    )
    op.create_index('ix_outbox_unpublished', 'outbox_events', ['id'], postgresql_where=sa.text('published_at IS NULL'))


def downgrade():
    op.drop_index('ix_outbox_unpublished', table_name='outbox_events', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_table('outbox_events')
