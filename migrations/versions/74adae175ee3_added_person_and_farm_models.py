"""added person and farm models

Revision ID: 74adae175ee3
Revises: 0ee302e73edb
Create Date: 2018-01-23 20:43:29.097886

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74adae175ee3'
down_revision = '0ee302e73edb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('farms',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('estimated_total_size', sa.Float(asdecimal=True), nullable=True),
    sa.Column('estimated_leased_size', sa.Float(asdecimal=True), nullable=True),
    sa.Column('estimated_owned_size', sa.Float(asdecimal=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('persons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('firstname', sa.String(length=200), nullable=False),
    sa.Column('lastname', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('person_to_farm',
    sa.Column('person_id', sa.Integer(), nullable=True),
    sa.Column('farm_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ),
    sa.ForeignKeyConstraint(['person_id'], ['persons.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('person_to_farm')
    op.drop_table('persons')
    op.drop_table('farms')
    # ### end Alembic commands ###
