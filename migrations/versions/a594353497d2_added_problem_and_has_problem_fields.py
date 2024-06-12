"""added problem and has problem fields

Revision ID: a594353497d2
Revises: 03504e182b3d
Create Date: 2024-05-28 14:28:35.673884

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a594353497d2'
down_revision = '03504e182b3d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_course_learning_activity_assessment_pairs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_problem', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('problem_detail', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('report_datetime', sa.DateTime(timezone=True), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_course_learning_activity_assessment_pairs', schema=None) as batch_op:
        batch_op.drop_column('report_datetime')
        batch_op.drop_column('problem_detail')
        batch_op.drop_column('has_problem')

    # ### end Alembic commands ###