"""add indexes for service invoice payment list

Revision ID: c4a9e3d2b1f0
Revises: 9f3d2b4c1a7e
Create Date: 2026-05-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4a9e3d2b1f0'
down_revision = '9f3d2b4c1a7e'
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name, index_name):
    return any(ix.get('name') == index_name for ix in inspector.get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _index_exists(inspector, 'service_invoices', 'ix_service_invoices_file_attached_at'):
        op.create_index(
            'ix_service_invoices_file_attached_at',
            'service_invoices',
            ['file_attached_at'],
            unique=False
        )

    if not _index_exists(inspector, 'service_invoices', 'ix_service_invoices_invoice_no'):
        op.create_index(
            'ix_service_invoices_invoice_no',
            'service_invoices',
            ['invoice_no'],
            unique=False
        )

    if not _index_exists(inspector, 'service_payments', 'ix_service_payments_invoice_cancel_created'):
        op.create_index(
            'ix_service_payments_invoice_cancel_created',
            'service_payments',
            ['invoice_id', 'cancelled_at', 'created_at'],
            unique=False
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, 'service_payments', 'ix_service_payments_invoice_cancel_created'):
        op.drop_index('ix_service_payments_invoice_cancel_created', table_name='service_payments')

    if _index_exists(inspector, 'service_invoices', 'ix_service_invoices_invoice_no'):
        op.drop_index('ix_service_invoices_invoice_no', table_name='service_invoices')

    if _index_exists(inspector, 'service_invoices', 'ix_service_invoices_file_attached_at'):
        op.drop_index('ix_service_invoices_file_attached_at', table_name='service_invoices')
