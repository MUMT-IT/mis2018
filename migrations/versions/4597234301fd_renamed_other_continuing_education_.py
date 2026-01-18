"""renamed other continuing education tables

Revision ID: 4597234301fd
Revises: 21d9c1bb6fbf
Create Date: 2026-01-18 17:13:03.389096

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4597234301fd'
down_revision = '21d9c1bb6fbf'
branch_labels = None
depends_on = None


def upgrade():
    # op.rename_table('organization_types', 'ce_organization_types')
    # op.rename_table('continuing_invoices', 'ce_invoices')
    # op.rename_table('members', 'ce_members')
    # op.rename_table('event_entities', 'ce_event_entities')
    # op.rename_table('member_addresses', 'ce_member_addresses')
    # op.rename_table('organizations', 'ce_organizations')
    # op.rename_table('register_payments', 'ce_register_payments')

    op.rename_table('occupations', 'ce_occupations')
    op.rename_table('member_types', 'ce_member_types')
    op.rename_table('genders', 'ce_genders')
    op.rename_table('age_ranges', 'ce_age_ranges')
    op.rename_table('registration_statuses', 'ce_registration_statuses')
    op.rename_table('register_payment_statuses', 'ce_register_payment_statuses')
    op.rename_table('certificate_types', 'ce_certificate_types')
    op.rename_table('member_certificate_statuses', 'ce_member_certificate_statuses')
    op.rename_table('entity_categories', 'ce_entity_categories')
    op.rename_table('member_registrations', 'ce_member_registrations')
    op.rename_table('register_payment_receipts', 'ce_register_payment_receipts')
    op.rename_table('speaker_profiles', 'ce_speaker_profiles')
    op.rename_table('event_speakers', 'ce_event_speakers')
    op.rename_table('event_agendas', 'ce_event_agendas')
    op.rename_table('event_materials', 'ce_event_materials')
    op.rename_table('event_registration_fees', 'ce_event_registration_fees')
    op.rename_table('event_editors', 'ce_event_editors')
    op.rename_table('event_registration_reviewers', 'ce_event_registration_reviewers')
    op.rename_table('event_payment_approvers', 'ce_event_payment_approvers')
    op.rename_table('event_receipt_issuers', 'ce_event_receipt_issuers')
    op.rename_table('event_certificate_managers', 'ce_event_certificate_managers')


    pass


def downgrade():
    op.rename_table('ce_occupations', 'occupations')
    op.rename_table('ce_member_types', 'member_types')
    op.rename_table('ce_genders', 'genders')
    op.rename_table('ce_age_ranges', 'age_ranges')
    op.rename_table('ce_registration_statuses', 'registration_statuses')
    op.rename_table('ce_register_payment_statuses', 'register_payment_statuses')
    op.rename_table('ce_certificate_types', 'certificate_types')
    op.rename_table('ce_member_certificate_statuses', 'member_certificate_statuses')
    op.rename_table('ce_entity_categories', 'entity_categories')
    op.rename_table('ce_member_registrations', 'member_registrations')
    op.rename_table('ce_register_payment_receipts', 'register_payment_receipts')
    op.rename_table('ce_speaker_profiles', 'speaker_profiles')
    op.rename_table('ce_event_speakers', 'event_speakers')
    op.rename_table('ce_event_agendas', 'event_agendas')
    op.rename_table('ce_event_materials', 'event_materials')
    op.rename_table('ce_event_registration_fees', 'event_registration_fees')
    op.rename_table('ce_event_editors', 'event_editors')
    op.rename_table('ce_event_registration_reviewers', 'event_registration_reviewers')
    op.rename_table('ce_event_payment_approvers', 'event_payment_approvers')
    op.rename_table('ce_event_receipt_issuers', 'event_receipt_issuers')
    op.rename_table('ce_event_certificate_managers', 'event_certificate_managers')
    pass
