"""Exercise staff login redirects without database or external services."""
import ast
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import parse_qs, urlsplit

from flask import Flask, Blueprint, abort, current_app, flash, redirect, request, session, url_for
from flask_admin.helpers import is_safe_url
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user

ROOT = Path(__file__).resolve().parents[1]


class LoginDestinationTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True)
        auth = Blueprint('auth', __name__)
        manager = LoginManager(app)
        manager.login_view = 'auth.login'

        class User(UserMixin):
            id = '42'
            is_active = True
            def verify_password(self, password):
                return password == 'correct'

        user = User()
        manager.user_loader(lambda user_id: user if user_id == user.id else None)
        query = SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(first=lambda: user))
        def form():
            return SimpleNamespace(
                email=SimpleNamespace(data=request.form.get('email', '')),
                password=SimpleNamespace(data=request.form.get('password', '')),
                remember_me=SimpleNamespace(data=False), errors={},
                validate_on_submit=lambda: request.method == 'POST',
            )
        namespace = dict(auth=auth, app=app, db=SimpleNamespace(session=SimpleNamespace(query=lambda *_: query)),
                         StaffAccount=User, LoginForm=form, current_user=current_user,
                         login_user=login_user, request=request, session=session,
                         current_app=current_app, redirect=redirect, url_for=url_for,
                         flash=flash, abort=abort, is_safe_url=is_safe_url,
                         _is_external_account=lambda *_: False,
                         _is_google_login_enabled=lambda: False,
                         identity_changed=SimpleNamespace(send=lambda *_args, **_kwargs: None),
                         Identity=lambda value: value, render_template=lambda *_args, **_kwargs: 'Login')
        source = ROOT / 'app/auth/views.py'
        names = {'login', '_handle_password_login', '_normalize_staff_email'}
        nodes = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
        app.register_blueprint(auth, url_prefix='/auth')
        app.add_url_rule('/', endpoint='index', view_func=lambda: 'Home')
        app.add_url_rule('/account', endpoint='auth.account', view_func=lambda: 'Account')
        module_namespace = dict(
            wraps=wraps, current_user=current_user, abort=abort,
            flask_login_required=login_required,
            FINANCE_SYSTEM='finance', PETTY_CASH_SYSTEM='petty_cash',
            ADVANCE_PAYMENT_SYSTEM='advance_payment',
            _selected_system=lambda: session.get('test_system'),
            _set_selected_system=lambda system: session.update(test_system=system),
            _can_use_module_system=lambda staff, system: system == 'finance',
        )
        module_source = ROOT / 'app/advance_payment/views.py'
        module_node = next(n for n in ast.parse(module_source.read_text()).body
                           if isinstance(n, ast.FunctionDef) and n.name == 'module_system_required')
        exec(compile(ast.Module(body=[module_node], type_ignores=[]), str(module_source), 'exec'), module_namespace)
        require_system = module_namespace['module_system_required']({'advance_payment', 'finance'})
        app.add_url_rule('/advance_payment/example/42', view_func=require_system(lambda: 'Requested document'))
        self.client = app.test_client()
        self.destination = '/advance_payment/example/42?tab=review&source=email'

    def login_url(self):
        response = self.client.get(self.destination)
        self.assertEqual(response.status_code, 302)
        location = response.headers['Location']
        self.assertEqual(parse_qs(urlsplit(location).query)['next'], [self.destination])
        return location

    def test_emailed_destination_after_successful_login(self):
        response = self.client.post(self.login_url(), data={'email': 'staff', 'password': 'correct'})
        self.assertEqual(response.headers['Location'], self.destination)
        self.assertEqual(self.client.get(response.headers['Location']).data, b'Requested document')

    def test_destination_survives_wrong_password(self):
        response = self.client.post(self.login_url(), data={'email': 'staff', 'password': 'wrong'})
        retry_url = response.headers['Location']
        self.assertEqual(parse_qs(urlsplit(retry_url).query)['next'], [self.destination])
        response = self.client.post(retry_url, data={'email': 'staff', 'password': 'correct'})
        self.assertEqual(response.headers['Location'], self.destination)

    def test_unsafe_destination_rejected_before_login(self):
        response = self.client.post('/auth/login?next=https://other.example/document',
                                    data={'email': 'staff', 'password': 'correct'})
        self.assertEqual(response.status_code, 400)
        with self.client.session_transaction() as state:
            self.assertNotIn('_user_id', state)


if __name__ == '__main__':
    unittest.main()
