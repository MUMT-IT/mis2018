import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from flask import Flask, abort, flash, redirect, request, url_for
from werkzeug.exceptions import NotFound

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('remaining, mismatch, fail', [(False, False, False),
    (True, False, False), (False, True, False), (False, False, True)])
def test_result_removal(remaining, mismatch, fail):
    tree = ast.parse((ROOT / 'app/eduqa/views.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == 'delete_student_skill_evidence_submission')
    node.decorator_list = []
    skill = NS(id=2, clos=[])
    clo = NS(id=3, course=NS(id=8, revision_id=1))
    skill.clos.append(clo)
    evidence = NS(id=4)
    student_evidence = NS(id=20, endorsed=True, endorsed_by='staff', endorsed_at='date')
    submission = NS(id=30)
    link = NS(session_id=40)
    evaluation = NS(id=40)
    session = Mock()
    if fail:
        session.commit.side_effect = RuntimeError('database failure')
    def model(record):
        q = Mock()
        q.get_or_404.return_value = record
        q.filter_by.return_value.first_or_404.return_value = record
        return NS(query=q)
    submission_model = model(submission)
    if mismatch:
        submission_model.query.filter_by.return_value.first_or_404.side_effect = NotFound()
    result_query = Mock()
    result_query.filter_by.return_value.all.return_value = [link]
    result_query.filter_by.return_value.first.return_value = NS(id=99) if remaining else None
    student_query = Mock()
    student_query.join.return_value.filter.return_value.first_or_404.return_value = NS(id=5)
    class Column:
        def __eq__(self, other):
            return True
    env = dict(EduQACurriculumnRevision=model(NS(id=1)), EduQASkill=model(skill),
        EduQACourseLearningOutcome=model(clo), EduQASkillEvidence=model(evidence),
        EduQAStudent=NS(query=student_query, id=Column()), EduQAEnrollment=NS(course_id=Column()),
        EduQAStudentSkillEvidence=model(student_evidence), DynamicFormSubmission=submission_model,
        EduQAEvaluationSessionResult=NS(query=result_query),
        EduQAEvaluationSession=NS(query=NS(get=lambda _: evaluation)), db=NS(session=session),
        abort=abort, flash=flash, redirect=redirect, request=request, url_for=url_for)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<result removal>', 'exec'), env)
    app = Flask(__name__)
    app.secret_key = 'test'
    app.add_url_rule('/results', endpoint='eduqa.view_student_skill_evidence_results', view_func=lambda: '')
    with app.test_request_context('/delete?bundle_id=9', method='POST'):
        if mismatch or fail:
            with pytest.raises(NotFound if mismatch else RuntimeError):
                env['delete_student_skill_evidence_submission'](1, 2, 3, 4, 5, 30)
        else:
            response = env['delete_student_skill_evidence_submission'](1, 2, 3, 4, 5, 30)
            assert 'bundle_id=9' in response.location
        submission_model.query.filter_by.assert_called_once_with(
            id=30, subject_type='eduqa_student_skill_evidence', subject_id=20)
        if mismatch:
            session.delete.assert_not_called()
        else:
            assert session.delete.call_args_list[0].args[0] is link
            assert session.delete.call_args_list[1].args[0] is submission
            assert any(call.args[0] is evaluation for call in session.delete.call_args_list) == (not remaining)
            assert student_evidence.endorsed is False
            assert student_evidence.endorsed_by is None
            assert student_evidence.endorsed_at is None
            assert session.rollback.called == fail
