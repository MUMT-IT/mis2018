"""added service model to com health

Revision ID: 87c39decd2eb
Revises: f229d16df79f
Create Date: 2019-03-03 18:47:56.723797

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '87c39decd2eb'
down_revision = 'f229d16df79f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('comhealth_services',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=True),
    sa.Column('location', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'comhealth_test_records', sa.Column('service_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'comhealth_test_records', 'comhealth_services', ['service_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'comhealth_test_records', type_='foreignkey')
    op.drop_column(u'comhealth_test_records', 'service_id')
    op.drop_table('comhealth_services')
    # ### end Alembic commands ###
