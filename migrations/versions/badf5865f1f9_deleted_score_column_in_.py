"""deleted score column in PAFunctionalCompetencyEvaluationIndicator table

Revision ID: badf5865f1f9
Revises: b7df0814152f
Create Date: 2023-11-29 09:13:50.655806

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'badf5865f1f9'
down_revision = 'b7df0814152f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_functional_competency_evaluation_indicators', schema=None) as batch_op:
        batch_op.drop_column('score')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_functional_competency_evaluation_indicators', schema=None) as batch_op:
        batch_op.add_column(sa.Column('score', sa.NUMERIC(), autoincrement=False, nullable=True))

    # ### end Alembic commands ###
