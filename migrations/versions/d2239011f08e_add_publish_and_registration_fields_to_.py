"""Add publish and registration fields to CEEventEntity

Revision ID: d2239011f08e
Revises: 09a42e926eaf
Create Date: 2026-02-19 10:01:39.064542

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd2239011f08e'
down_revision = '09a42e926eaf'
branch_labels = None
depends_on = None


def upgrade():
    # Add publish/registration columns to ce_event_entities
    with op.batch_alter_table('ce_event_entities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='Whether the event is publicly visible'))
        batch_op.add_column(sa.Column('registration_open', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='Whether registration is enabled'))
        batch_op.add_column(sa.Column('registration_open_at', sa.DateTime(timezone=True), nullable=True, comment='Registration open datetime'))
        batch_op.add_column(sa.Column('registration_close_at', sa.DateTime(timezone=True), nullable=True, comment='Registration close datetime'))


def downgrade():
    # Remove publish/registration columns from ce_event_entities
    with op.batch_alter_table('ce_event_entities', schema=None) as batch_op:
        batch_op.drop_column('registration_close_at')
        batch_op.drop_column('registration_open_at')
        batch_op.drop_column('registration_open')
        batch_op.drop_column('is_published')
