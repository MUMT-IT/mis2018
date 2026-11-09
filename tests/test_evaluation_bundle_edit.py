import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from flask import Flask, request

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('selected, saved', [(['11', '13'], True), (['11'], False), (['11', '999'], False)])
def test_edit_bundle_preserves_items_and_validates_selection(selected, saved):
    node = next(n for n in ast.parse((ROOT / 'app/eduqa/views.py').read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'create_evaluation_bundle')
    node.decorator_list = []
    class Column:
        def in_(self, values):
            return True
    clo = NS(id=3, course_id=8, course=NS(revision_id=1))
    skill = NS(id=2, clos=[clo])
    evidence = [NS(id=i, skill_id=i, clo_id=3, clo=clo, skill=NS(revision_id=1, clos=[clo])) for i in (4, 5, 6)]
    assignments = [NS(id=i, subject_id=e) for i, e in [(11, 4), (12, 5), (13, 6)]]
    kept, removed = NS(assignment_id=11), NS(assignment_id=12)
    bundle = NS(id=9, name='Old', items=[kept, removed])
    def model(record):
        q = Mock()
        q.get_or_404.return_value = record
        q.filter_by.return_value.first_or_404.return_value = record
        return NS(query=q)
    evidence_query, assignment_query = Mock(), Mock()
    evidence_query.join.return_value.filter.return_value.all.return_value = evidence
    assignment_query.filter_by.return_value.filter.return_value.all.return_value = assignments
    session = Mock()
    env = dict(EduQACurriculumnRevision=model(NS(id=1)), EduQASkill=model(skill),
        EduQACourseLearningOutcome=model(clo), EduQASkillEvidence=NS(query=evidence_query),
        DynamicFormAssignment=NS(query=assignment_query, subject_id=Column()),
        EduQAEvaluationBundle=model(bundle),
        EduQAEvaluationBundleItem=lambda assignment: NS(assignment_id=assignment.id),
        request=request, db=NS(session=session), current_user=NS(id=1),
        flash=lambda *_: None, abort=lambda *_: pytest.fail('unexpected abort'),
        url_for=lambda *_, **__: '/students', redirect=lambda url: url,
        render_template=lambda *_, **kw: kw)
    env['EduQACourseLearningOutcome'].course_id = Column()
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<bundle edit>', 'exec'), env)
    with Flask(__name__).test_request_context('/', method='POST', data={'name': 'Updated', 'assignments': selected}):
        env['create_evaluation_bundle'](1, 2, 3, 9)
    assert session.commit.called == saved
    if saved:
        assert bundle.name == 'Updated'
        assert bundle.items[0] is kept
        assert [item.assignment_id for item in bundle.items] == [11, 13]
        env['EduQAEvaluationBundle'].query.filter_by.assert_called_once_with(id=9, course_id=8)
    else:
        assert bundle.items == [kept, removed]
        assert bundle.name == 'Old'
