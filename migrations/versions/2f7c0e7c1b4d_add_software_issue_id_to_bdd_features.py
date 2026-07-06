"""add software_issue_id to bdd_features

Revision ID: 2f7c0e7c1b4d
Revises: 9a3fc269edf1
Create Date: 2026-06-22 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f7c0e7c1b4d'
down_revision = '9a3fc269edf1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('bdd_features', sa.Column('software_issue_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_bdd_features_software_issue_id'), 'bdd_features', ['software_issue_id'], unique=False)
    op.create_foreign_key(
        'fk_bdd_features_software_issue_id_software_issues',
        'bdd_features',
        'software_issues',
        ['software_issue_id'],
        ['id'],
    )


def downgrade():
    op.drop_constraint('fk_bdd_features_software_issue_id_software_issues', 'bdd_features', type_='foreignkey')
    op.drop_index(op.f('ix_bdd_features_software_issue_id'), table_name='bdd_features')
    op.drop_column('bdd_features', 'software_issue_id')
