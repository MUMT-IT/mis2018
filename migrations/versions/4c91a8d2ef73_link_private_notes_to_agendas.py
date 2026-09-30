"""link private notes to meeting agendas

Revision ID: 4c91a8d2ef73
Revises: f5982ff79b64
Create Date: 2026-09-30 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '4c91a8d2ef73'
down_revision = 'f5982ff79b64'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'meeting_agenda_notes',
        sa.Column('agenda_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_meeting_agenda_notes_agenda_id',
        'meeting_agenda_notes',
        'meeting_agendas',
        ['agenda_id'],
        ['id']
    )
    op.create_unique_constraint(
        'uq_meeting_agenda_note_agenda_staff',
        'meeting_agenda_notes',
        ['agenda_id', 'staff_id']
    )


def downgrade():
    op.drop_constraint(
        'uq_meeting_agenda_note_agenda_staff',
        'meeting_agenda_notes',
        type_='unique'
    )
    op.drop_constraint(
        'fk_meeting_agenda_notes_agenda_id',
        'meeting_agenda_notes',
        type_='foreignkey'
    )
    op.drop_column('meeting_agenda_notes', 'agenda_id')
