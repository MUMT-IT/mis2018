"""added an event category model

Revision ID: 3a905dc85402
Revises: da573c763b9c
Create Date: 2019-02-12 06:30:30.209204

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a905dc85402'
down_revision = 'da573c763b9c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('scheduler_event_categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'scheduler_room_reservations', sa.Column('category_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'scheduler_room_reservations', 'scheduler_event_categories', ['category_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'scheduler_room_reservations', type_='foreignkey')
    op.drop_column(u'scheduler_room_reservations', 'category_id')
    op.drop_table('scheduler_event_categories')
    # ### end Alembic commands ###
