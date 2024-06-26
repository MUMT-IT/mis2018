"""added updated_at column in PAScoreSheet table

Revision ID: fa69c8990e0f
Revises: fb252e8c7291
Create Date: 2023-09-04 20:12:38.046960

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa69c8990e0f'
down_revision = 'fb252e8c7291'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_score_sheets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_score_sheets', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

    # ### end Alembic commands ###
