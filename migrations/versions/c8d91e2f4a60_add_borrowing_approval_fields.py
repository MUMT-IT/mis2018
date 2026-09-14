"""Add finance-entered borrowing approval reference and date.

Revision ID: c8d91e2f4a60
Revises: 5a711386be3e
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d91e2f4a60"
down_revision = "5a711386be3e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cash_advance_borrowing_tickets") as batch_op:
        batch_op.add_column(sa.Column("borrowing_approval_ref_no", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("borrowing_approval_date", sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table("cash_advance_borrowing_tickets") as batch_op:
        batch_op.drop_column("borrowing_approval_date")
        batch_op.drop_column("borrowing_approval_ref_no")
