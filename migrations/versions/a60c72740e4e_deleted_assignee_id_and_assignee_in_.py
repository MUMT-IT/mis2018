"""Deleted assignee_id and assignee in ComplaintRecord model

Revision ID: a60c72740e4e
Revises: 466af8c17187
Create Date: 2024-06-21 15:35:25.926556

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a60c72740e4e'
down_revision = '466af8c17187'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_records', schema=None) as batch_op:
        batch_op.drop_constraint('complaint_records_assigned_id_fkey', type_='foreignkey')
        batch_op.drop_column('assigned_id')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('complaint_records', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assigned_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('complaint_records_assigned_id_fkey', 'complaint_admins', ['assigned_id'], ['id'])

    # ### end Alembic commands ###
