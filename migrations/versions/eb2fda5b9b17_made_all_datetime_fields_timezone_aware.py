"""made all datetime fields timezone aware

Revision ID: eb2fda5b9b17
Revises: b923d9d7a785
Create Date: 2019-01-04 10:10:33.213256

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb2fda5b9b17'
down_revision = 'b923d9d7a785'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="created_at", type_=sa.DateTime(timezone=True))
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="updated_at", type_=sa.DateTime(timezone=True))
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="cancalled_at", type_=sa.DateTime(timezone=True))
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="approved_at", type_=sa.DateTime(timezone=True))

def downgrade():
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="created_at", type_=sa.DateTime(timezone=False))
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="updated_at", type_=sa.DateTime(timezone=False))
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="cancalled_at", type_=sa.DateTime(timezone=False))
    op.alter_column(table_name='scheduler_room_reservations',
                    column_name="approved_at", type_=sa.DateTime(timezone=False))
