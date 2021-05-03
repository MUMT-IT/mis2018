"""changed the credit fields to numeric

Revision ID: b89d5e197b03
Revises: accdbea3a554
Create Date: 2021-04-19 14:14:23.273618

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b89d5e197b03'
down_revision = 'accdbea3a554'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('eduqa_courses', 'lecture_credit', type_=sa.Numeric())
    op.alter_column('eduqa_courses', 'lab_credit', type_=sa.Numeric())


def downgrade():
    op.alter_column('eduqa_courses', 'lecture_credit', type_=sa.Integer())
    op.alter_column('eduqa_courses', 'lab_credit', type_=sa.Integer())
