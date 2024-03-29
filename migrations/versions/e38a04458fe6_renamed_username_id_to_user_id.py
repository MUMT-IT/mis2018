"""Renamed username_id to user_id

Revision ID: e38a04458fe6
Revises: ee90d634034a
Create Date: 2023-02-10 14:25:22.170000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e38a04458fe6'
down_revision = 'ee90d634034a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('procurement_info_computers', 'erp_code_id',new_column_name='detail_id')
    op.alter_column('procurement_info_computers', 'username_id',new_column_name='user_id')
    op.drop_constraint(u'procurement_info_computers_username_id_fkey', 'procurement_info_computers', type_='foreignkey')
    op.drop_constraint(u'procurement_info_computers_erp_code_id_fkey', 'procurement_info_computers', type_='foreignkey')
    op.create_foreign_key(u'procurement_info_computers_user_id_fkey', 'procurement_info_computers', 'staff_account', ['user_id'], ['id'])
    op.create_foreign_key(u'procurement_info_computers_detail_id_fkey', 'procurement_info_computers', 'procurement_details', ['detail_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('procurement_info_computers', 'detail_id',new_column_name='erp_code_id')
    op.alter_column('procurement_info_computers', 'user_id',new_column_name='username_id')
    op.drop_constraint(u'procurement_info_computers_user_id_fkey', 'procurement_info_computers', type_='foreignkey')
    op.drop_constraint(u'procurement_info_computers_detail_id_fkey', 'procurement_info_computers', type_='foreignkey')
    op.create_foreign_key(u'procurement_info_computers_erp_code_id_fkey', 'procurement_info_computers', 'procurement_details', ['erp_code_id'], ['id'])
    op.create_foreign_key(u'procurement_info_computers_username_id_fkey', 'procurement_info_computers', 'staff_account', ['username_id'], ['id'])
    # ### end Alembic commands ###
