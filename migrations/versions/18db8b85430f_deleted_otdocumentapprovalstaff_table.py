"""deleted OtDocumentApprovalStaff table

Revision ID: 18db8b85430f
Revises: b0e85fe9abb8
Create Date: 2021-12-02 12:46:34.396511

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '18db8b85430f'
down_revision = 'b0e85fe9abb8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ot_document_approval_staff')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('ot_document_approval_staff',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('document_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('created_staff_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('staff_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['created_staff_id'], [u'staff_account.id'], name=u'ot_document_approval_staff_created_staff_id_fkey'),
    sa.ForeignKeyConstraint(['document_id'], [u'ot_document_approval.id'], name=u'ot_document_approval_staff_document_id_fkey'),
    sa.ForeignKeyConstraint(['staff_id'], [u'staff_account.id'], name=u'ot_document_approval_staff_staff_id_fkey'),
    sa.PrimaryKeyConstraint('id', name=u'ot_document_approval_staff_pkey')
    )
    # ### end Alembic commands ###
