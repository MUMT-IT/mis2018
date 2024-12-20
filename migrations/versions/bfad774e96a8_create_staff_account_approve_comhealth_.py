"""create staff_account approve comhealth_test_records table

Revision ID: bfad774e96a8
Revises: 22861fa6d52c
Create Date: 2024-09-09 15:46:18.816029

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bfad774e96a8'
down_revision = '22861fa6d52c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # op.drop_table('food_produce_breeds')
    # op.drop_table('food_parasite_tests')
    # op.drop_table('food_produces')
    # op.drop_table('buffer_details')
    # op.drop_table('food_agritype')
    # op.drop_table('food_parasite_results')
    # op.drop_table('food_toxico_tests')
    # op.drop_table('food_toxico_results')
    # op.drop_table('food_health_lab_tests')
    # op.drop_table('food_pesticide_tests')
    # op.drop_table('food_bact_tests')
    # op.drop_table('food_bact_results')
    # op.drop_table('buffers')
    # op.drop_table('market_types')
    # op.drop_table('farm_to_markets')
    # op.drop_table('market_details')
    # op.drop_table('food_farms')
    # op.drop_table('well_sizes')
    # op.drop_table('food_health_lab_results')
    # op.drop_table('food_survey_results')
    # op.drop_table('food_health_services')
    # op.drop_table('pesticide_uses')
    # op.drop_table('food_pesticide_results')
    # op.drop_table('well_types')
    # op.drop_table('food_health_phyexam')
    # op.drop_table('food_samples')
    # op.drop_table('food_person_and_farm')
    # op.drop_table('food_sample_lots')
    # op.drop_table('food_health_person')
    # op.drop_table('food_produce_and_farm')
    # op.drop_table('food_persons')
    # op.drop_table('food_grown_produces')
    with op.batch_alter_table('comhealth_test_records', schema=None) as batch_op:
        batch_op.add_column(sa.Column('staff_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'staff_account', ['staff_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('comhealth_test_records', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('staff_id')
    #
    # op.create_table('food_grown_produces',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_grown_produces_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('produce_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('breed_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('estimated_area', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['breed_id'], ['food_produce_breeds.id'], name='food_grown_produces_breed_id_fkey'),
    # sa.ForeignKeyConstraint(['produce_id'], ['food_produces.id'], name='food_grown_produces_produce_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_grown_produces_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_persons',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_persons_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('firstname', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    # sa.Column('lastname', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    # sa.Column('pid', sa.VARCHAR(length=13), autoincrement=False, nullable=True),
    # sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_persons_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_produce_and_farm',
    # sa.Column('farm_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('produce_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['farm_id'], ['food_farms.id'], name='food_produce_and_farm_farm_id_fkey'),
    # sa.ForeignKeyConstraint(['produce_id'], ['food_grown_produces.id'], name='food_produce_and_farm_produce_id_fkey')
    # )
    # op.create_table('food_health_person',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_health_person_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('cmscode', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('firstname', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('lastname', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('pid', sa.VARCHAR(length=13), autoincrement=False, nullable=True),
    # sa.Column('sex', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('age', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('mobile', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('title', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_health_person_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_sample_lots',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_sample_lots_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('collected_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    # sa.Column('registered_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    # sa.Column('farm_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['farm_id'], ['food_farms.id'], name='food_sample_lots_farm_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_sample_lots_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_person_and_farm',
    # sa.Column('person_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('farm_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['farm_id'], ['food_farms.id'], name='food_person_and_farm_farm_id_fkey'),
    # sa.ForeignKeyConstraint(['person_id'], ['food_persons.id'], name='food_person_and_farm_person_id_fkey')
    # )
    # op.create_table('food_samples',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_samples_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('lot_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('grown_produce_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['grown_produce_id'], ['food_grown_produces.id'], name='food_samples_grown_produce_id_fkey'),
    # sa.ForeignKeyConstraint(['lot_id'], ['food_sample_lots.id'], name='food_samples_lot_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_samples_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_health_phyexam',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_health_phyexam_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('cmscode', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('serviceno', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('servicedate', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    # sa.Column('weight', sa.NUMERIC(), autoincrement=False, nullable=True),
    # sa.Column('height', sa.NUMERIC(), autoincrement=False, nullable=True),
    # sa.Column('heartrate', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('systolic', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('diastolic', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_health_phyexam_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('well_types',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('well_types_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('desc', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='well_types_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_pesticide_results',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('test_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('sample_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('value', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.Column('cutoff_value', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['sample_id'], ['food_samples.id'], name='food_pesticide_results_sample_id_fkey'),
    # sa.ForeignKeyConstraint(['test_id'], ['food_pesticide_tests.id'], name='food_pesticide_results_test_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_pesticide_results_pkey')
    # )
    # op.create_table('pesticide_uses',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('pesticide_uses_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('desc', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.Column('last_use', sa.DATE(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='pesticide_uses_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_health_services',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('cmscode', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('serviceno', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('servicedate', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    # sa.Column('phyexam_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('labexam_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('health_person_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['health_person_id'], ['food_health_person.id'], name='food_health_services_health_person_id_fkey'),
    # sa.ForeignKeyConstraint(['labexam_id'], ['food_health_lab_results.id'], name='food_health_services_labexam_id_fkey'),
    # sa.ForeignKeyConstraint(['phyexam_id'], ['food_health_phyexam.id'], name='food_health_services_phyexam_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_health_services_pkey')
    # )
    # op.create_table('food_survey_results',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('pid', sa.VARCHAR(length=13), autoincrement=False, nullable=True),
    # sa.Column('firstname', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('lastname', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('results', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    # sa.Column('survey_datetime', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    # sa.Column('questions', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_survey_results_pkey')
    # )
    # op.create_table('food_health_lab_results',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('serviceno', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('data', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_health_lab_results_pkey')
    # )
    # op.create_table('well_sizes',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('well_sizes_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('desc', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='well_sizes_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_farms',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_farms_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('estimated_total_size', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.Column('estimated_leased_size', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.Column('estimated_owned_size', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.Column('agritype', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('district_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('province_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('subdistrict_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('street', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('village', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    # sa.Column('latitude', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.Column('longitude', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.Column('well_size_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('well_type_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('buffer_detail_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('buffer_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('pesticide_use_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('market_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['agritype'], ['food_agritype.id'], name='food_farms_agritype_fkey'),
    # sa.ForeignKeyConstraint(['buffer_detail_id'], ['buffer_details.id'], name='food_farms_buffer_detail_id_fkey'),
    # sa.ForeignKeyConstraint(['buffer_id'], ['buffers.id'], name='food_farms_buffer_id_fkey'),
    # sa.ForeignKeyConstraint(['district_id'], ['districts.id'], name='food_farms_district_id_fkey'),
    # sa.ForeignKeyConstraint(['market_id'], ['farm_to_markets.id'], name='food_farms_market_id_fkey'),
    # sa.ForeignKeyConstraint(['pesticide_use_id'], ['pesticide_uses.id'], name='food_farms_pesticide_use_id_fkey'),
    # sa.ForeignKeyConstraint(['province_id'], ['provinces.id'], name='food_farms_province_id_fkey'),
    # sa.ForeignKeyConstraint(['subdistrict_id'], ['subdistricts.id'], name='food_farms_subdistrict_id_fkey'),
    # sa.ForeignKeyConstraint(['well_size_id'], ['well_sizes.id'], name='food_farms_well_size_id_fkey'),
    # sa.ForeignKeyConstraint(['well_type_id'], ['well_types.id'], name='food_farms_well_type_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_farms_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('market_details',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('market_details_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('detail', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='market_details_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('farm_to_markets',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('farm_to_markets_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('market_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('market_detail_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['market_detail_id'], ['market_details.id'], name='farm_to_markets_market_detail_id_fkey'),
    # sa.ForeignKeyConstraint(['market_id'], ['market_types.id'], name='farm_to_markets_market_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='farm_to_markets_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('market_types',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('market_types_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('desc', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='market_types_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('buffers',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('buffers_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('desc', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='buffers_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_bact_results',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('test_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('sample_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('value', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['sample_id'], ['food_samples.id'], name='food_bact_results_sample_id_fkey'),
    # sa.ForeignKeyConstraint(['test_id'], ['food_bact_tests.id'], name='food_bact_results_test_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_bact_results_pkey')
    # )
    # op.create_table('food_bact_tests',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('method', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('unit', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_bact_tests_pkey')
    # )
    # op.create_table('food_pesticide_tests',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('unit', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('cutoff', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_pesticide_tests_pkey')
    # )
    # op.create_table('food_health_lab_tests',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('tcode', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('unit', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_health_lab_tests_pkey')
    # )
    # op.create_table('food_toxico_results',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('test_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('sample_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('value', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['sample_id'], ['food_samples.id'], name='food_toxico_results_sample_id_fkey'),
    # sa.ForeignKeyConstraint(['test_id'], ['food_toxico_tests.id'], name='food_toxico_results_test_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_toxico_results_pkey')
    # )
    # op.create_table('food_toxico_tests',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('unit', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.Column('cutoff', postgresql.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_toxico_tests_pkey')
    # )
    # op.create_table('food_parasite_results',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('test_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('sample_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('count', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.Column('comment', sa.VARCHAR(length=80), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['sample_id'], ['food_samples.id'], name='food_parasite_results_sample_id_fkey'),
    # sa.ForeignKeyConstraint(['test_id'], ['food_parasite_tests.id'], name='food_parasite_results_test_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_parasite_results_pkey')
    # )
    # op.create_table('food_agritype',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.Column('desc', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_agritype_pkey')
    # )
    # op.create_table('buffer_details',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('desc', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='buffer_details_pkey')
    # )
    # op.create_table('food_produces',
    # sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('food_produces_id_seq'::regclass)"), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.PrimaryKeyConstraint('id', name='food_produces_pkey'),
    # postgresql_ignore_search_path=False
    # )
    # op.create_table('food_parasite_tests',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('organism', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('stage', sa.VARCHAR(), autoincrement=False, nullable=True),
    # sa.PrimaryKeyConstraint('id', name='food_parasite_tests_pkey')
    # )
    # op.create_table('food_produce_breeds',
    # sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    # sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
    # sa.Column('produce_id', sa.INTEGER(), autoincrement=False, nullable=True),
    # sa.ForeignKeyConstraint(['produce_id'], ['food_produces.id'], name='food_produce_breeds_produce_id_fkey'),
    # sa.PrimaryKeyConstraint('id', name='food_produce_breeds_pkey')
    # )
    # ### end Alembic commands ###
