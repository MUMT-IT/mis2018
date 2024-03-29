"""added inform_score_at column in pa_agreements table

Revision ID: 48a6124e0fa6
Revises: 1df244d1aca7
Create Date: 2023-08-18 10:01:52.759142

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '48a6124e0fa6'
down_revision = '1df244d1aca7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_agreements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('inform_score_at', sa.DateTime(timezone=True), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_agreements', schema=None) as batch_op:
        batch_op.drop_column('inform_score_at')

    # ### end Alembic commands ###
