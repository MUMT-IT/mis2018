"""Deleted report_comment column in ComplaintPerformanceReport modal

Revision ID: 7c6195f9446f
Revises: 37fd6f61a1c4
Create Date: 2024-06-05 14:11:09.473174

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c6195f9446f'
down_revision = '37fd6f61a1c4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_performance_reports', schema=None) as batch_op:
        batch_op.drop_column('report_comment')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_performance_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('report_comment', sa.TEXT(), autoincrement=False, nullable=True))

    # ### end Alembic commands ###