"""created updated_at and confirm_at columns in PAFunctionalCompetencyEvaluation table

Revision ID: c6816d60f799
Revises: 34b8e95ff390
Create Date: 2023-11-22 14:29:46.977644

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6816d60f799'
down_revision = '34b8e95ff390'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_functional_competency_evaluations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('confirm_at', sa.DateTime(timezone=True), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_functional_competency_evaluations', schema=None) as batch_op:
        batch_op.drop_column('confirm_at')
        batch_op.drop_column('updated_at')

    # ### end Alembic commands ###
