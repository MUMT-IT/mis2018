"""link procurement plans to product codes

Revision ID: bb023f8215e9
Revises: aa912e7104d8
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'bb023f8215e9'
down_revision = 'aa912e7104d8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'procurement_plans',
        sa.Column('product_code_id', sa.String(length=12), nullable=True),
    )
    op.create_foreign_key(
        'fk_procurement_plans_product_code_id_product_codes',
        'procurement_plans',
        'product_codes',
        ['product_code_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Map legacy values only when they match a product-code ID, name, or the
    # standard "ID name" display value. Unmatched values remain available via
    # the legacy relationship for historical plans.
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE procurement_plans AS plans "
        "SET product_code_id = codes.id "
        "FROM procurement_output_project_reports AS reports, product_codes AS codes "
        "WHERE plans.output_project_report_id = reports.id "
        "AND ("
        "lower(trim(reports.name)) = lower(trim(codes.id)) "
        "OR lower(trim(reports.name)) = lower(trim(codes.name)) "
        "OR lower(trim(reports.name)) = lower(trim(codes.id || ' ' || codes.name))"
        ")"
    ))
    op.alter_column(
        'procurement_plans',
        'output_project_report_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    # Keep the legacy column nullable because newer plans may not have a legacy
    # value to restore after their ProductCode relationship is removed.
    op.drop_constraint(
        'fk_procurement_plans_product_code_id_product_codes',
        'procurement_plans',
        type_='foreignkey',
    )
    op.drop_column('procurement_plans', 'product_code_id')
