"""added payment group field to the profile model

Revision ID: 8ea8e029698a
Revises: f7ab974fd259
Create Date: 2019-11-11 21:26:58.562070

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ea8e029698a'
down_revision = 'f7ab974fd259'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_test_profiles', sa.Column('payment_group_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'comhealth_test_profiles', 'comhealth_payment_group', ['payment_group_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'comhealth_test_profiles', type_='foreignkey')
    op.drop_column('comhealth_test_profiles', 'payment_group_id')
    # ### end Alembic commands ###
