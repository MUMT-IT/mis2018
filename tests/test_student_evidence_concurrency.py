import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('existing, race, recovered', [(True, False, True),
    (False, False, False), (False, True, True), (False, True, False)])
def test_get_or_create_uses_savepoint(existing, race, recovered):
    tree = ast.parse((ROOT / 'app/eduqa/student_evidence.py').read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    record = NS(id=10)
    query = Mock()
    query.filter_by.return_value.first.side_effect = [record if existing else None, record if recovered else None]
    model = Mock(return_value=record)
    model.query = query
    session = Mock()
    from unittest.mock import MagicMock
    session.begin_nested.return_value = MagicMock()
    if race:
        session.flush.side_effect = IntegrityError('insert', {}, Exception())
    env = dict(db=NS(session=session), EduQAStudentSkillEvidence=model, IntegrityError=IntegrityError)
    exec(compile(tree, '<student evidence>', 'exec'), env)
    if race and not recovered:
        with pytest.raises(IntegrityError):
            env['get_or_create_student_evidence'](NS(id=1), NS(id=2), NS(id=3))
    else:
        assert env['get_or_create_student_evidence'](NS(id=1), NS(id=2), NS(id=3)) is record
    assert session.begin_nested.called == (not existing)
    session.rollback.assert_not_called()
    if not existing:
        model.assert_called_once_with(evidence_id=1, student_id=2, created_by_id=3)


def test_migration_merges_submissions_and_enforces_unique_pair():
    spec = importlib.util.spec_from_file_location('merge_migration', ROOT / 'migrations/versions/7c9d2e4f6a81_unique_student_skill_evidence.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('''CREATE TABLE eduqa_student_skill_evidence (
            id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, evidence_id INTEGER NOT NULL,
            url TEXT, endorsed BOOLEAN, endorsed_by_id INTEGER, endorsed_at TEXT)''')
        connection.exec_driver_sql('''CREATE TABLE dynamic_form_submissions (
            id INTEGER PRIMARY KEY, subject_type TEXT, subject_id INTEGER, respondent_id INTEGER)''')
        connection.exec_driver_sql("INSERT INTO eduqa_student_skill_evidence VALUES (1, 2, 3, NULL, 1, 7, 'date'), (4, 2, 3, 'url', 0, NULL, NULL), (5, 8, 3, 'other', 0, NULL, NULL)")
        connection.exec_driver_sql("INSERT INTO dynamic_form_submissions VALUES (10, 'eduqa_student_skill_evidence', 1, 7), (11, 'eduqa_student_skill_evidence', 4, 8), (12, 'other', 4, 9)")
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.exec_driver_sql('SELECT id FROM eduqa_student_skill_evidence ORDER BY id').all() == [(1,), (5,)]
        assert connection.exec_driver_sql('SELECT subject_id FROM dynamic_form_submissions ORDER BY id').all() == [(1,), (1,), (4,)]
        assert connection.exec_driver_sql('SELECT respondent_id FROM dynamic_form_submissions ORDER BY id').all() == [(7,), (8,), (9,)]
        assert connection.exec_driver_sql('SELECT url, endorsed, endorsed_by_id FROM eduqa_student_skill_evidence WHERE id=1').one() == ('url', 0, None)
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM eduqa_student_skill_evidence_merge_archive').scalar() == 2
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql('INSERT INTO eduqa_student_skill_evidence (id, student_id, evidence_id) VALUES (6, 2, 3)')
        migration.downgrade()
        assert connection.exec_driver_sql('SELECT COUNT(*) FROM dynamic_form_submissions').scalar() == 3
