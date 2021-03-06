"""added en/th title to personal info

Revision ID: d04730f7b864
Revises: 18ffa3d8d083
Create Date: 2020-11-07 11:08:58.289264

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd04730f7b864'
down_revision = '18ffa3d8d083'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('staff_personal_info', sa.Column('en_title', sa.String(), nullable=True))
    op.add_column('staff_personal_info', sa.Column('th_title', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('staff_personal_info', 'th_title')
    op.drop_column('staff_personal_info', 'en_title')
    # ### end Alembic commands ###
