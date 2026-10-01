"""add special work-from-home days

Revision ID: 5a7b9c1d3e42
Revises: 4c91a8d2ef73
"""
from alembic import op
import sqlalchemy as sa


revision = '5a7b9c1d3e42'
down_revision = '4c91a8d2ef73'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'staff_special_wfh_days',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('work_date'),
    )
    op.create_table(
        'staff_special_wfh_day_staff',
        sa.Column('special_day_id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['special_day_id'], ['staff_special_wfh_days.id']),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('special_day_id', 'staff_id'),
    )


def downgrade():
    op.drop_table('staff_special_wfh_day_staff')
    op.drop_table('staff_special_wfh_days')
