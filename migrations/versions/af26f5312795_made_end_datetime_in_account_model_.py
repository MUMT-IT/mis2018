"""made end datetime in account model nullable

Revision ID: af26f5312795
Revises: 67d823b17b7c
Create Date: 2021-12-07 15:43:29.060000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af26f5312795'
down_revision = '67d823b17b7c'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(table_name='tracker_accounts',
                    column_name='creation_date',
                    new_column_name='creation_datetime')
    op.alter_column(table_name='tracker_accounts',
                    column_name='end_date',
                    new_column_name='end_datetime',
                    nullable=True)


def downgrade():
    op.alter_column(table_name='tracker_accounts',
                    column_name='creation_datetime',
                    new_column_name='creation_date')
    op.alter_column(table_name='tracker_accounts',
                    column_name='end_datetime',
                    new_column_name='end_date',
                    nullable=False)
