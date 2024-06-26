"""created PAFunctionalCompetencyEvaluationIndicator table

Revision ID: 2e4c6ec52035
Revises: c6816d60f799
Create Date: 2023-11-22 14:40:39.298334

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2e4c6ec52035'
down_revision = 'c6816d60f799'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('pa_functional_competency_evaluation_indicators',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('evaluation_id', sa.Integer(), nullable=True),
    sa.Column('indicator_id', sa.Integer(), nullable=True),
    sa.Column('criterion_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['criterion_id'], ['pa_functional_competency_criteria.id'], ),
    sa.ForeignKeyConstraint(['evaluation_id'], ['pa_functional_competency_evaluations.id'], ),
    sa.ForeignKeyConstraint(['indicator_id'], ['pa_functional_competency_indicators.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('pa_functional_competency_evaluation_indicators')
    # ### end Alembic commands ###
