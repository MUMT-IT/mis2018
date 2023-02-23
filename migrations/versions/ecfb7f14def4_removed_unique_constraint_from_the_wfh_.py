"""removed unique constraint from the wfh job activity

Revision ID: ecfb7f14def4
Revises: eb6ac506a3cd
Create Date: 2022-06-28 22:08:25.810075

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ecfb7f14def4'
down_revision = 'eb6ac506a3cd'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(constraint_name='staff_work_from_home_job_detail_topic_key',
                             table_name='staff_work_from_home_job_detail',
                             type_='unique'
                             )


def downgrade():
    op.create_unique_constraint('staff_work_from_home_job_detail_topic_key',
                                'staff_work_from_home_job_detail',
                                ['topic'])
