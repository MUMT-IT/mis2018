"""added timezone to student check in record

Revision ID: a51e95225d74
Revises: 8a1efca06e2a
Create Date: 2018-02-08 05:52:59.257192

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a51e95225d74'
down_revision = '8a1efca06e2a'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('student_check_in_records', 'checkin',
            type_=sa.DateTime(timezone=True), nullable=False)


def downgrade():
    op.alter_column('student_check_in_records', 'checkin',
            type_=sa.DateTime(), nullable=False)
