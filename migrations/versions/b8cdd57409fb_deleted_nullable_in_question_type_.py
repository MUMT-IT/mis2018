"""Deleted nullable in question_type column for ComplaintRecord Model

Revision ID: b8cdd57409fb
Revises: 01ccd42fda23
Create Date: 2024-04-02 15:47:12.576179

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8cdd57409fb'
down_revision = '01ccd42fda23'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_records', schema=None) as batch_op:
        batch_op.alter_column('question_type',
               existing_type=sa.VARCHAR(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_records', schema=None) as batch_op:
        batch_op.alter_column('question_type',
               existing_type=sa.VARCHAR(),
               nullable=False)

    # ### end Alembic commands ###
