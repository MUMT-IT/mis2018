"""Added PurchaseTrackerForm model

Revision ID: 792e384fe549
Revises: fa5893033201
Create Date: 2022-06-30 21:10:29.369000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '792e384fe549'
down_revision = 'fa5893033201'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tracker_forms',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.Column('staff_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('method', sa.String(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.Date(), server_default=sa.text(u'now()'), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['tracker_accounts.id'], ),
    sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('tracker_forms')
    # ### end Alembic commands ###
