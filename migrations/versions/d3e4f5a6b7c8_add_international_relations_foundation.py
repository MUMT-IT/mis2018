"""Add the International Relations participant identity and staff admin role."""

from alembic import op
import sqlalchemy as sa


revision = 'd3e4f5a6b7c8'
down_revision = 'c2f45ae11edb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ir_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('google_subject', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('profile_image_url', sa.Text(), nullable=True),
        sa.Column('is_active_account', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_ir_participants_email'),
        sa.UniqueConstraint('google_subject', name='uq_ir_participants_google_subject'),
    )
    op.create_index('ix_ir_participants_email', 'ir_participants', ['email'])
    op.create_index(
        'ix_ir_participants_google_subject',
        'ir_participants',
        ['google_subject'],
    )
    op.execute(sa.text("""
        INSERT INTO roles (role_need, action_need, resource_id)
        SELECT 'international_relations_admin', NULL, NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM roles
            WHERE role_need = 'international_relations_admin'
              AND action_need IS NULL
              AND resource_id IS NULL
        )
    """))


def downgrade():
    op.execute(sa.text("""
        DELETE FROM user_roles
        WHERE role_id IN (
            SELECT id FROM roles
            WHERE role_need = 'international_relations_admin'
              AND action_need IS NULL
              AND resource_id IS NULL
        )
    """))
    op.execute(sa.text("""
        DELETE FROM roles
        WHERE role_need = 'international_relations_admin'
          AND action_need IS NULL
          AND resource_id IS NULL
    """))
    op.drop_index('ix_ir_participants_google_subject', table_name='ir_participants')
    op.drop_index('ix_ir_participants_email', table_name='ir_participants')
    op.drop_table('ir_participants')

