import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from flask import Flask, request
from werkzeug.datastructures import MultiDict

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('scoring', ROOT / 'app/dynamic_forms/scoring.py')
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)
namespace = {'score_is_in_range': scoring.score_is_in_range}
source = ast.parse((ROOT / 'app/eduqa/evaluation_bundles.py').read_text())
source.body = [n for n in source.body if not isinstance(n, ast.ImportFrom)]
exec(compile(source, '<bundle helper>', 'exec'), namespace)
bundle_answers = namespace['bundle_answers']


def sections():
    field = NS(id=1, label='Score', required=True, field_type='number',
               config={'scorable': True, 'max_score': 5, 'weight': 1})
    return [(NS(id=i, version=NS(fields=[field])),
             NS(id=i, skill=NS(name='Skill {}'.format(i)))) for i in (10, 20)]


def test_shared_form_fields_are_separate_per_assignment():
    answers, errors = bundle_answers(sections(), MultiDict({
        'assignment_10_field_1': '2', 'assignment_20_field_1': '5'}))
    assert not errors
    assert [answer[2][0][1] for answer in answers] == ['2', '5']


@pytest.mark.parametrize('second', ['', '6', 'invalid'])
def test_invalid_second_section_blocks_bundle(second):
    _, errors = bundle_answers(sections(), MultiDict({
        'assignment_10_field_1': '2', 'assignment_20_field_1': second}))
    assert errors


@pytest.mark.parametrize('fail_commit, invalid', [(False, False), (True, False), (False, True)])
def test_bundle_save_is_atomic(fail_commit, invalid):
    tree = ast.parse((ROOT / 'app/eduqa/views.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'fill_evaluation_bundle')
    node.decorator_list = []
    state = NS(added=[], committed=False, rolled_back=False)
    def commit():
        if fail_commit:
            raise RuntimeError('database failure')
        state.committed = True
    def rollback():
        state.rolled_back = True
    class Query:
        def get_or_404(self, _id):
            return NS(id=1, course_id=7)
        def join(self, *_args):
            return self
        def filter(self, *_args):
            return self
        def filter_by(self, **_kwargs):
            return self
        def first_or_404(self):
            return NS(id=42)
        def first(self):
            return None
    def model(**kwargs):
        return NS(id=99, **kwargs)
    def session_model(**kwargs):
        return NS(results=[], **kwargs)
    class Column:
        def __eq__(self, _other):
            return True
    env = dict(request=request, bundle_answers=bundle_answers,
        get_or_create_student_evidence=lambda *_: NS(id=99),
        EduQAEvaluationBundle=NS(query=Query()), _evaluation_bundle_sections=lambda _: sections(),
        EduQAStudent=NS(query=Query(), id=Column()), EduQAEnrollment=NS(course_id=Column()),
        EduQAStudentSkillEvidence=type('Evidence', (), {'query': Query(), '__new__': staticmethod(lambda cls, **kw: model(**kw))}),
        EduQAEvaluationSession=session_model, EduQAEvaluationSessionResult=model,
        DynamicFormSubmission=model, DynamicFormAnswer=model,
        current_user=NS(id=8), flash=lambda *_: None,
        redirect=lambda url: url, url_for=lambda *_, **kw: '/students',
        render_template=lambda *_, **kw: 'form',
        db=NS(session=NS(add=state.added.append, flush=lambda: None, commit=commit, rollback=rollback),
              func=NS(now=lambda: 'now')))
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<bundle route>', 'exec'), env)
    with Flask('test').test_request_context('/bundle', method='POST', data={
        'assignment_10_field_1': '2', 'assignment_20_field_1': '' if invalid else '5'}):
        if fail_commit:
            with pytest.raises(RuntimeError):
                env['fill_evaluation_bundle'](1, 42)
            assert state.rolled_back
            assert not state.committed
        else:
            env['fill_evaluation_bundle'](1, 42)
            assert state.committed == (not invalid)
            if invalid:
                assert not state.added
            else:
                evaluation = state.added[0]
                assert len(evaluation.results) == 2
                assert [r.submission.answers[0].value for r in evaluation.results] == ['2', '5']
                assert all(r.submission.subject_type == 'eduqa_student_skill_evidence' for r in evaluation.results)


def test_bundle_relationships_resolve_during_mapper_initialization():
    """Load actual model definitions in an isolated registry, without app services."""
    import subprocess
    import sys
    script = r'''
import ast
import sys
import types
from pathlib import Path
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, func
from sqlalchemy.orm import declarative_base, relationship, backref, configure_mappers
from types import SimpleNamespace
root = Path.cwd()
Base = declarative_base()
db = SimpleNamespace(Model=Base, Column=Column, Integer=Integer, ForeignKey=ForeignKey,
                     DateTime=DateTime, String=String, func=func, relationship=relationship,
                     backref=backref, UniqueConstraint=__import__('sqlalchemy').UniqueConstraint)
class StaffAccount(Base):
    __tablename__ = 'staff_account'
    id = Column(Integer, primary_key=True)
class EduQACourse(Base):
    __tablename__ = 'eduqa_courses'
    id = Column(Integer, primary_key=True)
class Student(Base):
    __tablename__ = 'eduqa_students'
    id = Column(Integer, primary_key=True)
class DynamicFormVersion(Base):
    __tablename__ = 'dynamic_form_versions'
    id = Column(Integer, primary_key=True)
import sqlalchemy as sa
for name in ('Boolean', 'Text', 'JSON', 'Float'):
    setattr(db, name, getattr(sa, name))
namespace = dict(db=db, StaffAccount=StaffAccount, func=func, DynamicFormVersion=DynamicFormVersion)
# Execute real dynamic model classes referenced by the new relationships.
tree = ast.parse((root / 'app/dynamic_forms/models.py').read_text())
classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in
           ('DynamicFormAssignment', 'DynamicFormSubmission', 'DynamicFormAnswer', 'DynamicFormField', 'DynamicFormOption')]
# Submission properties are inert here; provide the field's version target as well.
namespace.update(raw_score=lambda *a: None, weighted_score=lambda *a: None)
exec(compile(ast.Module(body=classes, type_ignores=[]), '<dynamic models>', 'exec'), namespace)
module = types.ModuleType('app.dynamic_forms.models')
module.DynamicFormAssignment = namespace['DynamicFormAssignment']
module.DynamicFormSubmission = namespace['DynamicFormSubmission']
sys.modules['app.dynamic_forms.models'] = module
namespace['EduQACourse'] = EduQACourse
tree = ast.parse((root / 'app/eduqa/models.py').read_text())
imports = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == 'app.dynamic_forms.models']
assert imports, 'Dynamic form targets must be loaded before configuring bundle mappers'
classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.startswith('EduQAEvaluation')]
exec(compile(ast.Module(body=imports + classes, type_ignores=[]), '<bundle models>', 'exec'), namespace)
configure_mappers()
assert namespace['EduQAEvaluationBundleItem'].assignment.property.mapper.class_ is module.DynamicFormAssignment
assert namespace['EduQAEvaluationSessionResult'].submission.property.mapper.class_ is module.DynamicFormSubmission
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
