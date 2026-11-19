"""Store prices for a ComHealth service at first check-in."""
from alembic import op
import sqlalchemy as sa

revision = 'c7e1f2a3b4d5'
down_revision = '63f1351bfcec'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comhealth_services', sa.Column('prices_frozen_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('comhealth_service_test_prices',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('service_id', sa.Integer, sa.ForeignKey('comhealth_services.id'), nullable=False),
        sa.Column('test_item_id', sa.Integer, sa.ForeignKey('comhealth_test_items.id'), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('service_id', 'test_item_id'))
    op.create_table('comhealth_service_profile_prices',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('service_id', sa.Integer, sa.ForeignKey('comhealth_services.id'), nullable=False),
        sa.Column('profile_id', sa.Integer, sa.ForeignKey('comhealth_test_profiles.id'), nullable=False),
        sa.Column('quote_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('service_id', 'profile_id'))


def downgrade():
    op.drop_table('comhealth_service_profile_prices')
    op.drop_table('comhealth_service_test_prices')
    op.drop_column('comhealth_services', 'prices_frozen_at')
