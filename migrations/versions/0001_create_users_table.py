"""create users table

Reviewed by hand against design.md, "User Service: database".

Revision ID: 0001
Revises: 
Create Date: 2026-11-16 17:41:51.124948

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('display_name', sa.String(length=64), nullable=False),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('status_text', sa.String(length=140), nullable=True),
    sa.Column('avatar_key', sa.String(length=255), nullable=True),
    sa.Column('avatar_version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('locale', sa.String(length=10), nullable=True),
    sa.Column('timezone', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )


def downgrade():
    op.drop_table('users')
