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


@pytest.mark.parametrize('has_answer, valid, conflict', [
    (False, True, False), (True, True, False),
    (False, False, False), (False, True, True),
])
def test_field_removal_protects_saved_answers(has_answer, valid, conflict):
    tree = ast.parse((ROOT / 'app/dynamic_forms/views.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'delete_field')
    node.decorator_list = []
    session = Mock()
    if conflict:
        session.commit.side_effect = IntegrityError('delete', {}, Exception())
    record = NS(id=12, version_id=7)
    answer_query = Mock()
    answer_query.filter_by.return_value.first.return_value = NS(value=None) if has_answer else None
    env = dict(DynamicFormDeleteForm=lambda: NS(validate_on_submit=lambda: valid),
               DynamicFormField=NS(query=NS(get_or_404=lambda _: record)),
               DynamicFormAnswer=NS(query=answer_query),
               db=NS(session=session), IntegrityError=IntegrityError,
               flash=flash, redirect=redirect, url_for=url_for)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<field removal>', 'exec'), env)
    app = Flask(__name__)
    app.secret_key = 'test'
    app.add_url_rule('/versions/<int:version_id>/edit', endpoint='dynamic_forms.edit_version',
                     view_func=lambda version_id: 'builder')
    app.add_url_rule('/fields/12/delete', view_func=lambda: env['delete_field'](12), methods=['POST'])
    client = app.test_client()
    response = client.post('/fields/12/delete')
    assert response.status_code == 302
    assert response.location == '/versions/7/edit'
    allowed = valid and not has_answer
    assert session.delete.called == allowed
    assert session.commit.called == allowed
    assert session.rollback.called == (allowed and conflict)
    if valid:
        answer_query.filter_by.assert_called_once_with(field_id=12)
    with client.session_transaction() as stored:
        category, _ = stored['_flashes'][0]
    assert category == ('success' if allowed and not conflict else 'danger' if not valid else 'warning')


def test_builder_displays_removal_and_feedback():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'))
    template = env.get_template('dynamic_forms/form_edit.html')
    env.globals.update(get_flashed_messages=lambda **_: [('success', 'Field removed.')],
                       url_for=lambda endpoint, **_: '/' + endpoint)
    field = NS(id=12, display_order=1, label='Score', key='score', field_type='number',
               config={}, required=False)
    context = template.new_context(dict(dynamic_form=NS(name='Evaluation'),
        version=NS(id=7, version=1, status='Draft', fields=[field]),
        form=[], passing_form=NS(hidden_tag=lambda: '', passing_percentage=NS(
            id='percentage', label=NS(text='Passing score'), description='',
            __call__=lambda **_: '')), delete_form=NS(hidden_tag=lambda: 'csrf')))
    # A callable field matches WTForms' rendering interface.
    class Percentage:
        id = 'percentage'
        label = NS(text='Passing score')
        description = ''
        def __call__(self, **kwargs):
            return ''
    context.vars['passing_form'] = NS(hidden_tag=lambda: '', passing_percentage=Percentage())
    class Form(list):
        def hidden_tag(self):
            return ''
    context.vars['form'] = Form()
    rendered = ''.join(template.blocks['page_content'](context))
    assert 'Field removed.' in rendered
    assert 'dynamic_forms.delete_field' in rendered
    assert 'return confirm(' in rendered
    assert 'csrf' in rendered
