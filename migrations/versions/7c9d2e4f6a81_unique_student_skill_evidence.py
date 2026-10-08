"""Merge duplicate student evidence and enforce one record per student/evidence.

Original duplicate rows are retained in an archive table for recovery.
"""
from alembic import op
import sqlalchemy as sa

revision = '7c9d2e4f6a81'
down_revision = '130a5ca32561'
branch_labels = None
depends_on = None

ARCHIVE = 'eduqa_student_skill_evidence_merge_archive'
CONSTRAINT = 'uq_student_skill_evidence_student_evidence'


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        op.execute('LOCK TABLE eduqa_student_skill_evidence, dynamic_form_submissions IN ACCESS EXCLUSIVE MODE')
    # Keep every original duplicate row, including URLs and endorsement metadata.
    op.execute(f'''CREATE TABLE {ARCHIVE} AS
        SELECT * FROM (
            SELECT e.*, MIN(id) OVER (PARTITION BY student_id, evidence_id) AS canonical_id,
                   COUNT(*) OVER (PARTITION BY student_id, evidence_id) AS duplicate_count
            FROM eduqa_student_skill_evidence e
        ) duplicates WHERE duplicate_count > 1''')
    groups = connection.execute(sa.text(f'SELECT DISTINCT canonical_id FROM {ARCHIVE}')).scalars().all()
    for canonical_id in groups:
        rows = connection.execute(sa.text(
            f'SELECT * FROM {ARCHIVE} WHERE canonical_id = :id ORDER BY id'),
            {'id': canonical_id}).mappings().all()
        for row in rows:
            if row['id'] == canonical_id:
                continue
            connection.execute(sa.text('''UPDATE dynamic_form_submissions SET subject_id = :canonical
                WHERE subject_type = 'eduqa_student_skill_evidence' AND subject_id = :duplicate'''),
                {'canonical': canonical_id, 'duplicate': row['id']})
            connection.execute(sa.text('DELETE FROM eduqa_student_skill_evidence WHERE id = :id'),
                               {'id': row['id']})
        # The combined results must be reviewed again before endorsement.
        url = next((row['url'] for row in rows if row['url']), None)
        connection.execute(sa.text('''UPDATE eduqa_student_skill_evidence
            SET url = :url, endorsed = :endorsed, endorsed_by_id = NULL, endorsed_at = NULL
            WHERE id = :id'''), {'url': url, 'endorsed': False, 'id': canonical_id})
    with op.batch_alter_table('eduqa_student_skill_evidence') as batch:
        batch.create_unique_constraint(CONSTRAINT, ['student_id', 'evidence_id'])


def downgrade():
    with op.batch_alter_table('eduqa_student_skill_evidence') as batch:
        batch.drop_constraint(CONSTRAINT, type_='unique')
    # Keep merged results and the archive; splitting records would hide results again.
