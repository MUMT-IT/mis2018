"""Add indexes for ComHealth customer list

Revision ID: b8c4f2a91d3e
Revises: 483932b0b8fd
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b8c4f2a91d3e'
down_revision = '483932b0b8fd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comhealth_test_records', schema=None) as batch_op:
        batch_op.create_index('ix_comhealth_test_records_service_id', ['service_id'], unique=False)
        batch_op.create_index('ix_comhealth_test_records_service_labno', ['service_id', 'labno'], unique=False)
        batch_op.create_index('ix_comhealth_test_records_service_customer', ['service_id', 'customer_id'], unique=False)
        batch_op.create_index('ix_comhealth_test_records_service_checkin',
                              ['service_id', 'checkin_datetime'],
                              unique=False)


def downgrade():
    with op.batch_alter_table('comhealth_test_records', schema=None) as batch_op:
        batch_op.drop_index('ix_comhealth_test_records_service_checkin')
        batch_op.drop_index('ix_comhealth_test_records_service_customer')
        batch_op.drop_index('ix_comhealth_test_records_service_labno')
        batch_op.drop_index('ix_comhealth_test_records_service_id')
