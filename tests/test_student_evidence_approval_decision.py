import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('endorsed, decision, evaluator, expected', [
    (True, True, False, True),
    (True, False, True, False),
    (False, True, False, False),
    (False, False, True, True),
    (True, None, False, False),
    (False, None, None, None),
])
def test_approval_decision_precedence(endorsed, decision, evaluator, expected):
    tree = ast.parse((ROOT / 'app/eduqa/models.py').read_text())
    model = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                 and n.name == 'EduQAStudentSkillEvidence')
    method = next(n for n in model.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'effective_passed')
    env = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<approval>', 'exec'), env)
    record = SimpleNamespace(endorsed=endorsed, endorsed_passed=decision)
    assert env['effective_passed'](record, SimpleNamespace(passed=evaluator)) is expected
    if not endorsed or decision is None:
        assert env['effective_passed'](record, None) is None
