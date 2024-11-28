"""Added ship_type column in ServiceSampleAppointments model

Revision ID: e94dde60f3c4
Revises: 885301f8e3a5
Create Date: 2024-11-22 15:33:39.417049

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e94dde60f3c4'
down_revision = '885301f8e3a5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_sample_appointments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ship_type', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_sample_appointments', schema=None) as batch_op:
        batch_op.drop_column('ship_type')
    # ### end Alembic commands ###