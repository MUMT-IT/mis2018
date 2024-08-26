"""Added detail column in ComplaintPerformanceReport modal

Revision ID: c13c18a15cd8
Revises: e31f711a23d1
Create Date: 2024-06-05 14:27:35.265065

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c13c18a15cd8'
down_revision = 'e31f711a23d1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_performance_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('detail', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_performance_reports', schema=None) as batch_op:
        batch_op.drop_column('detail')

    # ### end Alembic commands ###