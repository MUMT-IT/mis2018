"""Add HR check-in request revocation audit fields."""
from alembic import op
import sqlalchemy as sa

revision = '7b8c9d0e1f23'
down_revision = '63f1351bfcec'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('staff_request_work_logins', sa.Column('revoked_approved_at', sa.DateTime(timezone=True)))
    op.add_column('staff_request_work_logins', sa.Column('revoked_by_id', sa.Integer()))
    op.add_column('staff_request_work_logins', sa.Column('revocation_reason', sa.Text()))
    op.create_foreign_key('fk_checkin_request_revoked_by', 'staff_request_work_logins', 'staff_account', ['revoked_by_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_checkin_request_revoked_by', 'staff_request_work_logins', type_='foreignkey')
    op.drop_column('staff_request_work_logins', 'revocation_reason')
    op.drop_column('staff_request_work_logins', 'revoked_by_id')
    op.drop_column('staff_request_work_logins', 'revoked_approved_at')
