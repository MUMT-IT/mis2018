"""restore dropped staff seminar indexes

Revision ID: 9f3d2b4c1a7e
Revises: 6ec79a0163cd
Create Date: 2026-05-30 23:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f3d2b4c1a7e'
down_revision = '6ec79a0163cd'
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name, index_name):
    return any(ix.get('name') == index_name for ix in inspector.get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _index_exists(inspector, 'staff_seminar_attends', 'ix_staff_seminar_attends_batch_id'):
        op.create_index('ix_staff_seminar_attends_batch_id', 'staff_seminar_attends', ['batch_id'], unique=False)

    if not _index_exists(inspector, 'staff_seminar_attends', 'ix_staff_seminar_attends_created_by_id'):
        op.create_index('ix_staff_seminar_attends_created_by_id', 'staff_seminar_attends', ['created_by_id'], unique=False)

    if not _index_exists(inspector, 'staff_seminar_batches', 'ix_staff_seminar_batches_created_by_id'):
        op.create_index('ix_staff_seminar_batches_created_by_id', 'staff_seminar_batches', ['created_by_id'], unique=False)

    if not _index_exists(inspector, 'staff_seminar_batches', 'ix_staff_seminar_batches_seminar_id'):
        op.create_index('ix_staff_seminar_batches_seminar_id', 'staff_seminar_batches', ['seminar_id'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, 'staff_seminar_attends', 'ix_staff_seminar_attends_batch_id'):
        op.drop_index('ix_staff_seminar_attends_batch_id', table_name='staff_seminar_attends')

    if _index_exists(inspector, 'staff_seminar_attends', 'ix_staff_seminar_attends_created_by_id'):
        op.drop_index('ix_staff_seminar_attends_created_by_id', table_name='staff_seminar_attends')

    if _index_exists(inspector, 'staff_seminar_batches', 'ix_staff_seminar_batches_created_by_id'):
        op.drop_index('ix_staff_seminar_batches_created_by_id', table_name='staff_seminar_batches')

    if _index_exists(inspector, 'staff_seminar_batches', 'ix_staff_seminar_batches_seminar_id'):
        op.drop_index('ix_staff_seminar_batches_seminar_id', table_name='staff_seminar_batches')
