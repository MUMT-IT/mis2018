import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from flask import Flask, flash, redirect, url_for
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('assignments, submissions, valid, conflict', [
    (0, 0, True, False), (1, 0, True, False),
    (0, 1, True, False), (0, 0, False, False), (0, 0, True, True),
])
def test_removal_result_is_reported(assignments, submissions, valid, conflict):
    tree = ast.parse((ROOT / 'app/dynamic_forms/views.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'delete')
    node.decorator_list = []
    session = Mock()
    if conflict:
        session.commit.side_effect = IntegrityError('delete', {}, Exception())
    # Put references on an older version to ensure every version is checked.
    record = NS(versions=[NS(assignments=[1] * assignments, submissions=[1] * submissions),
                          NS(assignments=[], submissions=[])])
    env = dict(DynamicFormDeleteForm=lambda: NS(validate_on_submit=lambda: valid),
               DynamicForm=NS(query=NS(get_or_404=lambda _: record)),
               db=NS(session=session), IntegrityError=IntegrityError,
               flash=flash, redirect=redirect, url_for=url_for)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<removal route>', 'exec'), env)
    app = Flask(__name__)
    app.secret_key = 'test'
    app.add_url_rule('/', endpoint='dynamic_forms.index', view_func=lambda: 'index')
    app.add_url_rule('/1/delete', view_func=lambda: env['delete'](1), methods=['POST'])
    client = app.test_client()
    response = client.post('/1/delete')
    assert response.status_code == 302
    allowed = valid and not assignments and not submissions
    assert session.delete.called == allowed
    assert session.commit.called == allowed
    assert session.rollback.called == (allowed and conflict)
    with client.session_transaction() as stored:
        category, message = stored['_flashes'][0]
    assert category == ('success' if allowed and not conflict else 'danger' if not valid else 'warning')
    if assignments or submissions:
        assert str(assignments) in message and str(submissions) in message


def test_index_displays_removal_messages():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'))
    template = env.get_template('dynamic_forms/index.html')
    env.globals.update(get_flashed_messages=lambda **_: [('warning', 'Removal blocked')],
                       url_for=lambda *_, **__: '/', request=NS(args={}))
    # Render the page block directly to avoid unrelated base navigation dependencies.
    context = template.new_context(dict(forms=[]))
    assert 'Removal blocked' in ''.join(template.blocks['page_content'](context))
