"""created IDPLearningType table

Revision ID: fccc52d3cc64
Revises: 0bf4c1978d1f
Create Date: 2024-01-09 14:26:18.910810

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fccc52d3cc64'
down_revision = '0bf4c1978d1f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('idp_learning_type',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('type', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('idp_learning_type')
    # ### end Alembic commands ###
