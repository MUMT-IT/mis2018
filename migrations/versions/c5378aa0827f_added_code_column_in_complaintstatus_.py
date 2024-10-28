"""Added code column in ComplaintStatus model

Revision ID: c5378aa0827f
Revises: d91806e66ec5
Create Date: 2024-06-11 14:26:56.824668

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5378aa0827f'
down_revision = 'd91806e66ec5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_statuses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('code', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_statuses', schema=None) as batch_op:
        batch_op.drop_column('code')

    # ### end Alembic commands ###