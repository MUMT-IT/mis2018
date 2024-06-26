"""changed the schema of the Role model to accommodate flask-principal

Revision ID: 1f41d4e2b6da
Revises: ed16fe7ed7a9
Create Date: 2022-07-12 06:43:22.063000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f41d4e2b6da'
down_revision = 'ed16fe7ed7a9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('roles', sa.Column('action_need', sa.String(), nullable=True))
    op.add_column('roles', sa.Column('resource_id', sa.Integer(), nullable=True))
    op.add_column('roles', sa.Column('role_need', sa.String(), nullable=True))
    op.drop_constraint(u'roles_name_key', 'roles', type_='unique')
    op.drop_column('roles', 'app_name')
    op.drop_column('roles', 'name')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('roles', sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('roles', sa.Column('app_name', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.create_unique_constraint(u'roles_name_key', 'roles', ['name'])
    op.drop_column('roles', 'role_need')
    op.drop_column('roles', 'resource_id')
    op.drop_column('roles', 'action_need')
    # ### end Alembic commands ###
