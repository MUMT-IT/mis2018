import os
import sys
import types
from types import SimpleNamespace

from flask import Flask
from flask_login import LoginManager


class _DummyResponse:
    status_code = 200

    def json(self):
        return {}

    def raise_for_status(self):
        return None


def _install_import_stubs(app):
    pydrive_auth_stub = types.ModuleType('pydrive.auth')

    class GoogleAuth:
        def __init__(self, *args, **kwargs):
            self.credentials = None

    class ServiceAccountCredentials:
        @classmethod
        def from_json_keyfile_dict(cls, *args, **kwargs):
            return object()

    pydrive_auth_stub.GoogleAuth = GoogleAuth
    pydrive_auth_stub.ServiceAccountCredentials = ServiceAccountCredentials
    sys.modules['pydrive.auth'] = pydrive_auth_stub

    pydrive_drive_stub = types.ModuleType('pydrive.drive')

    class GoogleDrive:
        def __init__(self, *args, **kwargs):
            pass

    pydrive_drive_stub.GoogleDrive = GoogleDrive
    sys.modules['pydrive.drive'] = pydrive_drive_stub

    staff_pkg_stub = types.ModuleType('app.staff')
    staff_pkg_stub.__path__ = []
    sys.modules['app.staff'] = staff_pkg_stub

    staff_models_stub = types.ModuleType('app.staff.models')

    class StaffLeaveApprover:
        pass

    class _StaffAccountQuery:
        def filter_by(self, **kwargs):
            return self

        def first(self):
            return None

    class StaffAccount:
        query = _StaffAccountQuery()

        @classmethod
        def get_account_by_external_email(cls, email):
            registry = app.config.setdefault('BEHAVE_USER_REGISTRY', {})
            return registry.get((email or '').strip().lower())

    staff_models_stub.StaffAccount = StaffAccount
    staff_models_stub.StaffLeaveApprover = StaffLeaveApprover
    sys.modules['app.staff.models'] = staff_models_stub

    main_stub = types.ModuleType('app.main')
    main_stub.app = app
    main_stub.db = SimpleNamespace(session=SimpleNamespace(
        add=lambda *args, **kwargs: None,
        commit=lambda *args, **kwargs: None,
        query=lambda *args, **kwargs: SimpleNamespace(filter_by=lambda **_kwargs: SimpleNamespace(first=lambda: None)),
    ))
    main_stub.mail = SimpleNamespace(send=lambda *args, **kwargs: None)
    sys.modules['app.main'] = main_stub


def before_all(context):
    os.environ.setdefault('SECRET_KEY', 'behave-test-secret')

    app = Flask('behave-test')
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY=os.environ['SECRET_KEY'],
        LINE_CLIENT_ID='behave-line-client-id',
        LINE_CLIENT_SECRET='behave-line-client-secret',
        LINE_MESSAGE_API_ACCESS_TOKEN='behave-line-access-token',
        LINE_MESSAGE_API_CLIENT_SECRET='behave-line-message-secret',
        PUBLIC_BASE_URL='http://localhost',
        SERVER_NAME='localhost',
        PREFERRED_URL_SCHEME='http',
    )

    _install_import_stubs(app)

    from app.auth import authbp as auth_blueprint

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        registry = app.config.setdefault('BEHAVE_USER_REGISTRY', {})
        return registry.get(str(user_id))

    @app.route('/external')
    def external_landing():
        return (
            'External Employee Portal\n'
            'External employee access only\n'
        )

    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    context.app = app
    context.login_manager = login_manager
    context.app_context = app.app_context()
    context.app_context.push()


def after_all(context):
    if hasattr(context, 'app_context'):
        context.app_context.pop()


def before_scenario(context, scenario):
    context.client = context.app.test_client()
    context.patches = []
    context.fake_user = None
    context.app.config['BEHAVE_USER_REGISTRY'] = {}


def after_scenario(context, scenario):
    while context.patches:
        context.patches.pop().stop()
