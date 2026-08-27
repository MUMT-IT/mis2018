"""Create reusable output/project/report options for procurement plans

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
"""
from alembic import op
import sqlalchemy as sa


revision = 'f9a0b1c2d3e4'
down_revision = 'e8f9a0b1c2d3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'procurement_output_project_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.add_column(
        'procurement_plans',
        sa.Column('output_project_report_id', sa.Integer(), nullable=True),
    )

    bind = op.get_bind()
    existing_values = bind.execute(sa.text(
        'SELECT DISTINCT output_project_report '
        'FROM procurement_plans WHERE output_project_report IS NOT NULL'
    )).fetchall()
    for row in existing_values:
        bind.execute(
            sa.text('INSERT INTO procurement_output_project_reports (name) VALUES (:name)'),
            {'name': row[0]},
        )

    bind.execute(sa.text(
        'UPDATE procurement_plans AS plans '
        'SET output_project_report_id = reports.id '
        'FROM procurement_output_project_reports AS reports '
        'WHERE reports.name = plans.output_project_report'
    ))
    op.alter_column('procurement_plans', 'output_project_report_id', nullable=False)
    op.create_foreign_key(
        'fk_procurement_plans_output_project_report_id',
        'procurement_plans', 'procurement_output_project_reports',
        ['output_project_report_id'], ['id'],
    )
    op.drop_column('procurement_plans', 'output_project_report')


def downgrade():
    op.add_column('procurement_plans', sa.Column('output_project_report', sa.Text(), nullable=True))
    bind = op.get_bind()
    bind.execute(sa.text(
        'UPDATE procurement_plans AS plans '
        'SET output_project_report = reports.name '
        'FROM procurement_output_project_reports AS reports '
        'WHERE reports.id = plans.output_project_report_id'
    ))
    op.drop_constraint(
        'fk_procurement_plans_output_project_report_id',
        'procurement_plans', type_='foreignkey',
    )
    op.drop_column('procurement_plans', 'output_project_report_id')
    op.alter_column('procurement_plans', 'output_project_report', nullable=False)
    op.drop_table('procurement_output_project_reports')
