"""Add participant-managed International Relations profile fields."""

from alembic import op
import sqlalchemy as sa


revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ir_participants', sa.Column('preferred_name', sa.String(length=100), nullable=True))
    op.add_column('ir_participants', sa.Column('phone', sa.String(length=50), nullable=True))
    op.add_column('ir_participants', sa.Column('nationality', sa.String(length=100), nullable=True))
    op.add_column('ir_participants', sa.Column('home_institution', sa.String(length=255), nullable=True))
    op.add_column('ir_participants', sa.Column('department', sa.String(length=255), nullable=True))
    op.add_column('ir_participants', sa.Column('research_topic', sa.Text(), nullable=True))
    op.add_column('ir_participants', sa.Column('emergency_contact_name', sa.String(length=200), nullable=True))
    op.add_column('ir_participants', sa.Column('emergency_contact_phone', sa.String(length=50), nullable=True))


def downgrade():
    op.drop_column('ir_participants', 'emergency_contact_phone')
    op.drop_column('ir_participants', 'emergency_contact_name')
    op.drop_column('ir_participants', 'research_topic')
    op.drop_column('ir_participants', 'department')
    op.drop_column('ir_participants', 'home_institution')
    op.drop_column('ir_participants', 'nationality')
    op.drop_column('ir_participants', 'phone')
    op.drop_column('ir_participants', 'preferred_name')
