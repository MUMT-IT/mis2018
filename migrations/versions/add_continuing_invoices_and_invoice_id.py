"""add continuing_invoices table and invoice_id column

Revision ID: add_continuing_invoices_and_invoice_id
Revises: 309524de26b6
Create Date: 2025-12-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_continuing_invoices_and_invoice_id'
down_revision = '309524de26b6'
branch_labels = None
depends_on = None


def upgrade():
    # Create continuing_invoices table
    op.create_table(
        'continuing_invoices',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('invoice_no', sa.String(length=100), nullable=True),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('event_entity_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    # Add foreign keys for member_id and event_entity_id
    op.create_foreign_key(
        'fk_continuing_invoices_member_id', 'continuing_invoices', 'members', ['member_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_continuing_invoices_event_entity_id', 'continuing_invoices', 'event_entities', ['event_entity_id'], ['id'], ondelete='CASCADE'
    )

    # Add invoice_id column to register_payments
    op.add_column('register_payments', sa.Column('invoice_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_register_payments_invoice_id', 'register_payments', 'continuing_invoices', ['invoice_id'], ['id'], ondelete='CASCADE'
    )


def downgrade():
    # Drop foreign key and column from register_payments
    try:
        op.drop_constraint('fk_register_payments_invoice_id', 'register_payments', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_column('register_payments', 'invoice_id')
    except Exception:
        pass

    # Drop continuing_invoices table
    try:
        op.drop_constraint('fk_continuing_invoices_member_id', 'continuing_invoices', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_constraint('fk_continuing_invoices_event_entity_id', 'continuing_invoices', type_='foreignkey')
    except Exception:
        pass
    op.drop_table('continuing_invoices')
