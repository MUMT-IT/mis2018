"""Added created_at and sequence column in SoftwareRequestTimeline model

Revision ID: 8d20b3ecc2aa
Revises: c66beb5221f3
Create Date: 2025-04-25 15:40:11.636953

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8d20b3ecc2aa'
down_revision = 'c66beb5221f3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    with op.batch_alter_table('software_request_timelines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sequence', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('software_request_timelines', schema=None) as batch_op:
        batch_op.drop_column('created_at')
        batch_op.drop_column('sequence')
    # ### end Alembic commands ###
