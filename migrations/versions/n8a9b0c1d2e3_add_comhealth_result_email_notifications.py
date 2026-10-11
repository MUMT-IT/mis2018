"""add ComHealth result email notification audit log

Revision ID: n8a9b0c1d2e3
Revises: m7g8h9i0j1k2
Create Date: 2026-10-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'n8a9b0c1d2e3'
down_revision = 'm7g8h9i0j1k2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'comhealth_result_email_notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('service_no', sa.String(length=32), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('approval_status', sa.String(length=16), nullable=False),
        sa.Column('email_type', sa.String(length=32), nullable=False),
        sa.Column('template_name', sa.String(length=255), nullable=False),
        sa.Column('delivery_status', sa.String(length=16), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_by_staff_id', sa.Integer(), nullable=True),
        sa.Column('sent_by_fullname', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_comhealth_result_email_notifications_service_no',
        'comhealth_result_email_notifications', ['service_no'], unique=False,
    )
    op.create_index(
        'ix_comhealth_result_email_notifications_delivery_status',
        'comhealth_result_email_notifications', ['delivery_status'], unique=False,
    )
    op.create_index(
        'ix_comhealth_result_email_notifications_sent_at',
        'comhealth_result_email_notifications', ['sent_at'], unique=False,
    )
    op.create_index(
        'ix_comhealth_result_email_notifications_service_delivery_sent',
        'comhealth_result_email_notifications',
        ['service_no', 'delivery_status', 'sent_at'], unique=False,
    )


def downgrade():
    op.drop_index(
        'ix_comhealth_result_email_notifications_service_delivery_sent',
        table_name='comhealth_result_email_notifications',
    )
    op.drop_index(
        'ix_comhealth_result_email_notifications_sent_at',
        table_name='comhealth_result_email_notifications',
    )
    op.drop_index(
        'ix_comhealth_result_email_notifications_delivery_status',
        table_name='comhealth_result_email_notifications',
    )
    op.drop_index(
        'ix_comhealth_result_email_notifications_service_no',
        table_name='comhealth_result_email_notifications',
    )
    op.drop_table('comhealth_result_email_notifications')
