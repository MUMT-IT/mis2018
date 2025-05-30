"""Addedappointment_date, room_id and room column in SoftwareRequestDetail model

Revision ID: a2dc7dcdaa4b
Revises: 8d20b3ecc2aa
Create Date: 2025-04-25 15:56:11.936542

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a2dc7dcdaa4b'
down_revision = '8d20b3ecc2aa'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('software_request_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column('appointment_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('room_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'scheduler_room_resources', ['room_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('software_request_details', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('room_id')
        batch_op.drop_column('appointment_date')
    # ### end Alembic commands ###
