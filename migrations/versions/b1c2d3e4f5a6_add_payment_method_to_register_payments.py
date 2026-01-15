"""add payment_method to register_payments

Revision ID: b1c2d3e4f5a6
Revises: 7a2f52f1e55f, add_continuing_invoices_and_invoice_id
Create Date: 2026-01-13

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = ('7a2f52f1e55f', 'add_continuing_invoices_and_invoice_id')
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('register_payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_method', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('register_payments', schema=None) as batch_op:
        batch_op.drop_column('payment_method')
