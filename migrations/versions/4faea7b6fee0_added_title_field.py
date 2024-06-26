"""added title field

Revision ID: 4faea7b6fee0
Revises: 110ff6bea6f9
Create Date: 2023-06-07 15:10:43.789198

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4faea7b6fee0'
down_revision = '110ff6bea6f9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_course_assignment_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_course_assignment_sessions', schema=None) as batch_op:
        batch_op.drop_column('title')

    # ### end Alembic commands ###
