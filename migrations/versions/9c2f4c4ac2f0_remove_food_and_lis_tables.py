"""remove food and lis tables

Revision ID: 9c2f4c4ac2f0
Revises: 50585d469351
Create Date: 2026-05-18 20:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c2f4c4ac2f0'
down_revision = '50585d469351'
branch_labels = None
depends_on = None


def _drop_table_if_exists(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(table_name):
        op.drop_table(table_name)


def upgrade():
    # Drop LIS tables first because the blueprint code has already been removed.
    _drop_table_if_exists('lis_results')
    _drop_table_if_exists('lis_orders')
    _drop_table_if_exists('lis_tests')
    _drop_table_if_exists('lis_test_groups')
    _drop_table_if_exists('student_profile')

    # Drop Food tables in reverse dependency order.
    _drop_table_if_exists('food_bact_results')
    _drop_table_if_exists('food_parasite_results')
    _drop_table_if_exists('food_toxico_results')
    _drop_table_if_exists('food_pesticide_results')
    _drop_table_if_exists('food_health_services')
    _drop_table_if_exists('food_samples')
    _drop_table_if_exists('food_person_and_farm')
    _drop_table_if_exists('food_produce_and_farm')
    _drop_table_if_exists('food_sample_lots')
    _drop_table_if_exists('food_health_person')
    _drop_table_if_exists('food_health_lab_results')
    _drop_table_if_exists('food_health_phyexam')
    _drop_table_if_exists('food_health_lab_tests')
    _drop_table_if_exists('food_bact_tests')
    _drop_table_if_exists('food_parasite_tests')
    _drop_table_if_exists('food_toxico_tests')
    _drop_table_if_exists('food_pesticide_tests')
    _drop_table_if_exists('food_grown_produces')
    _drop_table_if_exists('food_produce_breeds')
    _drop_table_if_exists('food_produces')
    _drop_table_if_exists('food_farms')
    _drop_table_if_exists('food_persons')
    _drop_table_if_exists('food_agritype')
    _drop_table_if_exists('farm_to_markets')
    _drop_table_if_exists('market_types')
    _drop_table_if_exists('market_details')
    _drop_table_if_exists('pesticide_uses')
    _drop_table_if_exists('buffers')
    _drop_table_if_exists('buffer_details')
    _drop_table_if_exists('well_types')
    _drop_table_if_exists('well_sizes')


def downgrade():
    raise NotImplementedError(
        'Downgrade is intentionally unsupported for the food/lis table removal. '
        'Restore from backup if rollback is required.'
    )
