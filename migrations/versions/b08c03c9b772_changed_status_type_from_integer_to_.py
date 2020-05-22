"""changed status type from integer to boolean

Revision ID: b08c03c9b772
Revises: 9646fc7b894d
Create Date: 2020-05-22 15:32:05.359917

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b08c03c9b772'
down_revision = '9646fc7b894d'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('staff_work_from_home_job_detail',
                    column_name='status', type_=sa.Boolean(),
                    server_default=False,
                    postgresql_using='CASE WHEN status=0 THEN FALSE ELSE TRUE END;'
                    )


def downgrade():
    op.alter_column('staff_work_from_home_job_detail',
                    column_name='status', type_=sa.Integer(),
                    postgresql_using='CASE WHEN status=TRUE THEN 1 ELSE 0 END;'
                    )
