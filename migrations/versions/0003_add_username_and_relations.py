"""add users.username and user_relations

Reviewed by hand against design.md, "User Service: database". user_relations did not exist
yet, so it is created here together with the username column and the prefix-search index.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable on purpose: existing rows get their username at their next authenticated request.
    op.add_column('users', sa.Column('username', sa.String(length=255), nullable=True))
    op.create_unique_constraint(op.f('uq_users_username'), 'users', ['username'])
    # varchar_pattern_ops lets prefix searches (LIKE 'abc%') use an index in any collation.
    op.create_index(
        'ix_users_username_prefix', 'users', ['username'],
        postgresql_ops={'username': 'varchar_pattern_ops'},
    )

    op.create_table('user_relations',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('other_user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('contact', 'pending', 'blocked')", name=op.f('ck_user_relations_kind')),
    sa.ForeignKeyConstraint(['other_user_id'], ['users.id'], name=op.f('fk_user_relations_other_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_relations_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'other_user_id', name=op.f('pk_user_relations'))
    )
    op.create_index('ix_user_relations_other_user_id', 'user_relations', ['other_user_id'])


def downgrade():
    op.drop_index('ix_user_relations_other_user_id', table_name='user_relations')
    op.drop_table('user_relations')
    op.drop_index('ix_users_username_prefix', table_name='users', postgresql_ops={'username': 'varchar_pattern_ops'})
    op.drop_constraint(op.f('uq_users_username'), 'users', type_='unique')
    op.drop_column('users', 'username')
