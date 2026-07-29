"""bridge missing procurement migration revision

Revision ID: d655065274c1
Revises: 7b0d1f6c2a9e
Create Date: 2026-06-12 00:00:00.000000

This no-op bridge restores the Alembic revision graph for the
qr_code_attached procurement migration.
"""


# revision identifiers, used by Alembic.
revision = 'd655065274c1'
down_revision = '7b0d1f6c2a9e'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
