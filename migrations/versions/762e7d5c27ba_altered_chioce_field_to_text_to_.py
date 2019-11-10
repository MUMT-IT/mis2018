"""altered chioce field to text to accomodate a long list of choices

Revision ID: 762e7d5c27ba
Revises: 3f53b91034a4
Create Date: 2019-11-10 05:35:14.060765

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '762e7d5c27ba'
down_revision = '3f53b91034a4'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(table_name='comhealth_customer_info_items',
                    column_name='choices',
                    type_=sa.Text(),
                   )


def downgrade():
    op.alter_column(table_name='comhealth_customer_info_items',
                    column_name='choices',
                    type_=sa.String(128),
                   )
