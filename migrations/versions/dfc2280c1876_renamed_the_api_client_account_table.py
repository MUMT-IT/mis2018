"""renamed the api_client_account table

Revision ID: dfc2280c1876
Revises: 2d383a8976bf
Create Date: 2022-08-24 06:03:03.625318

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dfc2280c1876'
down_revision = '2d383a8976bf'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('api_client_accounts', 'scb_payment_service_client_accounts')


def downgrade():
    op.rename_table('scb_payment_service_client_accounts', 'api_client_accounts')
