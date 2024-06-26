"""Edited nullable in question_type column for ComplaintRecord Model

Revision ID: a4fa35e6428d
Revises: de91431a70f7
Create Date: 2024-04-02 15:30:19.198975

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4fa35e6428d'
down_revision = 'de91431a70f7'
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
               nullable=True)

    # ### end Alembic commands ###
