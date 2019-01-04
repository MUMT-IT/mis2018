"""added timezone to date fields in scheduler_room_reservations

Revision ID: b923d9d7a785
Revises: 0d2a321a1e58
Create Date: 2019-01-04 10:03:36.286300

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b923d9d7a785'
down_revision = '0d2a321a1e58'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(table_name='scheduler_room_reservations',
                        column_name="start", type_=sa.DateTime(timezone=True))
    op.alter_column(table_name='scheduler_room_reservations',
                        column_name="end", type_=sa.DateTime(timezone=True))


def downgrade():
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="start", type_=sa.DateTime(timezone=False))
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="end", type_=sa.DateTime(timezone=False))
