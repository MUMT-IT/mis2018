"""add seminar batch and created_by column in staff_seminar_attends table

Revision ID: c1b2a3d4e5f6
Revises: f94421c49dad
Create Date: 2026-03-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1b2a3d4e5f6'
down_revision = 'f94421c49dad'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'staff_seminar_batches',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('seminar_id', sa.Integer(), sa.ForeignKey('staff_seminar.id'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('staff_account.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('note', sa.String(), nullable=True),
    )
    op.create_index('ix_staff_seminar_batches_created_by_id', 'staff_seminar_batches', ['created_by_id'])
    op.create_index('ix_staff_seminar_batches_seminar_id', 'staff_seminar_batches', ['seminar_id'])

    with op.batch_alter_table('staff_seminar_attends', schema=None) as batch_op:
        batch_op.add_column(sa.Column('batch_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_staff_seminar_attends_batch_id', 'staff_seminar_batches',
                                    ['batch_id'], ['id'])
        batch_op.create_foreign_key('fk_staff_seminar_attends_created_by_id', 'staff_account',
                                    ['created_by_id'], ['id'])
        batch_op.create_index('ix_staff_seminar_attends_batch_id', ['batch_id'])
        batch_op.create_index('ix_staff_seminar_attends_created_by_id', ['created_by_id'])


def downgrade():
    with op.batch_alter_table('staff_seminar_attends', schema=None) as batch_op:
        batch_op.drop_index('ix_staff_seminar_attends_created_by_id')
        batch_op.drop_index('ix_staff_seminar_attends_batch_id')
        batch_op.drop_constraint('fk_staff_seminar_attends_created_by_id', type_='foreignkey')
        batch_op.drop_constraint('fk_staff_seminar_attends_batch_id', type_='foreignkey')
        batch_op.drop_column('created_by_id')
        batch_op.drop_column('batch_id')

    op.drop_index('ix_staff_seminar_batches_seminar_id', table_name='staff_seminar_batches')
    op.drop_index('ix_staff_seminar_batches_created_by_id', table_name='staff_seminar_batches')
    op.drop_table('staff_seminar_batches')
