"""Enhance member profile details with organization and addresses

Revision ID: 7a2f52f1e55f
Revises: 13bf0bb35049
Create Date: 2025-09-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a2f52f1e55f'
down_revision = '13bf0bb35049'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'organization_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=False),
        sa.Column('name_th', sa.String(length=150), nullable=True),
        sa.Column('is_user_defined', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name_en')
    )

    op.create_table(
        'occupations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name_en', sa.String(length=150), nullable=False),
        sa.Column('name_th', sa.String(length=150), nullable=True),
        sa.Column('is_user_defined', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name_en')
    )

    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('organization_type_id', sa.Integer(), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('is_user_defined', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_type_id'], ['organization_types.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.add_column('members', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.add_column('members', sa.Column('occupation_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_members_organization', 'members', 'organizations', ['organization_id'], ['id'])
    op.create_foreign_key('fk_members_occupation', 'members', 'occupations', ['occupation_id'], ['id'])

    op.create_table(
        'member_addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('address_type', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('line1', sa.String(length=255), nullable=False),
        sa.Column('line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=True),
        sa.Column('state', sa.String(length=120), nullable=True),
        sa.Column('postal_code', sa.String(length=50), nullable=True),
        sa.Column('country_code', sa.String(length=2), nullable=True),
        sa.Column('country_name', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_member_addresses_member_id', 'member_addresses', ['member_id'])

    organization_types = [
        {'name_en': 'Government/Private', 'name_th': 'รัฐ/เอกชน'},
        {'name_en': 'Laboratory', 'name_th': 'คลินิกเทคนิคการแพทย์'},
        {'name_en': 'Primary Healthcare', 'name_th': 'โรงพยาบาลขนาดเล็ก'},
        {'name_en': 'Secondary Healthcare', 'name_th': 'โรงพยาบาลขนาดกลาง'},
        {'name_en': 'Tertiary Healthcare', 'name_th': 'โรงพยาบาลขนาดใหญ่'},
        {'name_en': 'Specialized Clinic', 'name_th': 'คลินิกเฉพาะทาง'},
        {'name_en': 'Academic Institute', 'name_th': 'สถาบันการศึกษา'},
        {'name_en': 'Other (Please specify)', 'name_th': 'อื่น ๆ (โปรดระบุ)'}
    ]
    op.bulk_insert(sa.table('organization_types',
                             sa.column('name_en', sa.String),
                             sa.column('name_th', sa.String),
                             sa.column('is_user_defined', sa.Boolean)),
                   [{'name_en': item['name_en'], 'name_th': item['name_th'], 'is_user_defined': False}
                    for item in organization_types])

    occupations = [
        {'name_en': 'Medical Technologist', 'name_th': 'นักเทคนิคการแพทย์'},
        {'name_en': 'Radiologist', 'name_th': 'นักรังสีเทคนิค'},
        {'name_en': 'Scientist', 'name_th': 'นักวิทยาศาสตร์'},
        {'name_en': 'Researcher', 'name_th': 'นักวิจัย'},
        {'name_en': 'College Professor', 'name_th': 'อาจารย์มหาวิทยาลัย'},
        {'name_en': 'Other', 'name_th': 'อื่น ๆ'}
    ]
    op.bulk_insert(sa.table('occupations',
                             sa.column('name_en', sa.String),
                             sa.column('name_th', sa.String),
                             sa.column('is_user_defined', sa.Boolean)),
                   [{'name_en': item['name_en'], 'name_th': item['name_th'], 'is_user_defined': False}
                    for item in occupations])


def downgrade():
    op.drop_index('ix_member_addresses_member_id', table_name='member_addresses')
    op.drop_table('member_addresses')
    op.drop_constraint('fk_members_occupation', 'members', type_='foreignkey')
    op.drop_constraint('fk_members_organization', 'members', type_='foreignkey')
    op.drop_column('members', 'occupation_id')
    op.drop_column('members', 'organization_id')
    op.drop_table('organizations')
    op.drop_table('occupations')
    op.drop_table('organization_types')
