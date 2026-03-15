"""add questionnaire_completed_at to ce_member_registrations

Revision ID: 6b3d0ea47a6e
Revises: da4f28072560
Create Date: 2026-02-26 11:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6b3d0ea47a6e'
down_revision = 'da4f28072560'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ce_member_registrations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'questionnaire_completed_at',
                sa.DateTime(timezone=True),
                nullable=True,
                comment='When the member completed the post-course questionnaire',
            )
        )


def downgrade():
    with op.batch_alter_table('ce_member_registrations', schema=None) as batch_op:
        batch_op.drop_column('questionnaire_completed_at')
