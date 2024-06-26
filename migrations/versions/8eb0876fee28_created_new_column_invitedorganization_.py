"""created new column (invitedorganization)) in staff_seminar_attends table

Revision ID: 8eb0876fee28
Revises: 3af46ab7b737
Create Date: 2022-08-05 11:34:58.205672

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8eb0876fee28'
down_revision = '3af46ab7b737'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('staff_seminar_attends', sa.Column('invited_organization', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('staff_seminar_attends', 'invited_organization')
    # ### end Alembic commands ###
