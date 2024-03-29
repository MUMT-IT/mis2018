"""Updated procurement number is unique

Revision ID: 790af1bd2463
Revises: fa23c1e06dab
Create Date: 2022-09-12 15:30:23.148000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '790af1bd2463'
down_revision = 'fa23c1e06dab'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('procurement_purchasing_types',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('purchasing_type', sa.String(), nullable=True),
    sa.Column('fund', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'procurement_details', sa.Column('curr_acq_value', sa.Float(), nullable=True))
    op.add_column(u'procurement_details', sa.Column('purchasing_type_id', sa.Integer(), nullable=True))
    op.add_column(u'procurement_details', sa.Column('sub_number', sa.Integer(), nullable=True))
    op.alter_column(u'procurement_details', 'budget_year',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column(u'procurement_details', 'name',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.alter_column(u'procurement_details', 'procurement_no',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.create_unique_constraint(None, 'procurement_details', ['procurement_no'])
    op.create_foreign_key(None, 'procurement_details', 'procurement_purchasing_types', ['purchasing_type_id'], ['id'])
    op.drop_column(u'procurement_details', 'purchasing_type')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(u'procurement_details', sa.Column('purchasing_type', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'procurement_details', type_='foreignkey')
    op.drop_constraint(None, 'procurement_details', type_='unique')
    op.alter_column(u'procurement_details', 'procurement_no',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column(u'procurement_details', 'name',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.alter_column(u'procurement_details', 'budget_year',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.drop_column(u'procurement_details', 'sub_number')
    op.drop_column(u'procurement_details', 'purchasing_type_id')
    op.drop_column(u'procurement_details', 'curr_acq_value')
    op.drop_table('procurement_purchasing_types')
    # ### end Alembic commands ###
