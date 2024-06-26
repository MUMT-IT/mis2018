"""created new requester_self_added column in StaffLeaveType

Revision ID: 391031663214
Revises: c6bd42254613
Create Date: 2022-06-06 12:06:11.081620

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '391031663214'
down_revision = 'c6bd42254613'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('staff_leave_types', sa.Column('requester_self_added', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('staff_leave_types', 'requester_self_added')
    # ### end Alembic commands ###
