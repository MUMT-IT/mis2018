"""added suggestion field and plan update field

Revision ID: f79c128372d2
Revises: bc79668d3df4
Create Date: 2024-06-26 09:39:41.077655

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f79c128372d2'
down_revision = 'bc79668d3df4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grade_deviation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('course_suggestion', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_courses', schema=None) as batch_op:
        batch_op.drop_column('course_suggestion')
        batch_op.drop_column('grade_deviation')

    # ### end Alembic commands ###
