"""replaced course Id with CLO Id

Revision ID: 90e0d97bf004
Revises: c981a763d55d
Create Date: 2023-08-30 13:56:17.516699

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90e0d97bf004'
down_revision = 'c981a763d55d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_course_learning_activity_assessment_pairs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('clo_id', sa.Integer(), nullable=True))
        batch_op.drop_constraint('eduqa_course_learning_activity_assessment_pairs_course_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(None, 'eduqa_course_learning_outcomes', ['clo_id'], ['id'])
        batch_op.drop_column('course_id')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('eduqa_course_learning_activity_assessment_pairs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('course_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('eduqa_course_learning_activity_assessment_pairs_course_id_fkey', 'eduqa_courses', ['course_id'], ['id'])
        batch_op.drop_column('clo_id')

    # ### end Alembic commands ###
