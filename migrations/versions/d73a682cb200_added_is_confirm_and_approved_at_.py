"""Added is_confirm and approved_at columns in ServiceQuotation model

Revision ID: d73a682cb200
Revises: e538eca7b4c7
Create Date: 2025-06-11 15:44:34.880182

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd73a682cb200'
down_revision = 'e538eca7b4c7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_quotations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('is_confirm', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_quotations', schema=None) as batch_op:
        batch_op.drop_column('is_confirm')
        batch_op.drop_column('approved_at')
    # ### end Alembic commands ###
