"""Added origin in ComplaintRecord model

Revision ID: 2275d855a8fb
Revises: 865c846872f4
Create Date: 2023-08-24 16:43:29.381077

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2275d855a8fb'
down_revision = '865c846872f4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_records', schema=None) as batch_op:
        batch_op.add_column(sa.Column('origin_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'complaint_records', ['origin_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_records', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('origin_id')

    # ### end Alembic commands ###
