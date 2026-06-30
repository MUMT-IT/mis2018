import os
import tempfile
from pathlib import Path

from sqlalchemy import event


_TEST_TABLE_NAMES = [
    'roles',
    'user_roles',
    'orgs',
    'staff_personal_info',
    'staff_employments',
    'staff_job_positions',
    'staff_academic_position',
    'staff_academic_position_records',
    'staff_account',
    'service_admins',
    'staff_leave_types',
    'staff_leave_quota',
    'staff_leave_used_quota',
    'staff_work_logins',
    'staff_request_work_logins',
    'ot_payment_announce',
    'ot_timeslots',
    'ot_job_roles',
    'ot_compensation_rate',
    'ot_document_approval',
    'ot_announce_document_assoc',
    'ot_staff_assoc',
    'ot_round_request',
    'ot_shifts',
    'ot_record',
]


def _selected_tables(db):
    return [db.metadata.tables[name] for name in _TEST_TABLE_NAMES if name in db.metadata.tables]


def _reset_selected_tables(db):
    tables = _selected_tables(db)
    if not tables:
        raise RuntimeError('No BDD test tables were registered')
    db.session.remove()
    db.metadata.drop_all(bind=db.engine, tables=tables)
    db.metadata.create_all(bind=db.engine, tables=tables)


def _pop_app_context_if_active(context):
    app_context = getattr(context, 'app_context', None)
    if app_context is None:
        return
    if getattr(app_context, '_cv_tokens', None):
        app_context.pop()


def before_all(context):
    os.environ.setdefault('SECRET_KEY', 'behave-test-secret')
    os.environ.setdefault('PUBLIC_BASE_URL', 'http://localhost')
    os.environ.setdefault('LINE_CLIENT_ID', 'behave-line-client-id')
    os.environ.setdefault('LINE_CLIENT_SECRET', 'behave-line-client-secret')
    os.environ.setdefault('LINE_MESSAGE_API_ACCESS_TOKEN', 'behave-line-access-token')
    os.environ.setdefault('LINE_MESSAGE_API_CLIENT_SECRET', 'behave-line-message-secret')
    fd, db_path = tempfile.mkstemp(prefix='behave-mis-', suffix='.sqlite3')
    os.close(fd)
    context.db_path = db_path
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

    from app.main import app, db

    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SERVER_NAME='localhost',
        PREFERRED_URL_SCHEME='http',
    )
    app.jinja_env.globals.setdefault('csrf_token', lambda: '')

    context.app = app
    context.db = db
    context.app_context = app.app_context()
    context.app_context.push()
    if db.engine.url.get_backend_name() == 'sqlite':
        @event.listens_for(db.engine, 'connect')
        def _register_sqlite_timezone(dbapi_connection, _connection_record):
            dbapi_connection.create_function('timezone', 2, lambda _tz, value: value)
    _reset_selected_tables(db)


def after_all(context):
    _pop_app_context_if_active(context)
    if getattr(context, 'db_path', None):
        try:
            Path(context.db_path).unlink(missing_ok=True)
        except TypeError:
            if Path(context.db_path).exists():
                Path(context.db_path).unlink()


def before_scenario(context, scenario):
    _pop_app_context_if_active(context)
    context.app_context = context.app.app_context()
    context.app_context.push()
    context.client = context.app.test_client()
    context.app.jinja_env.globals.setdefault('csrf_token', lambda: '')
    with context.client.session_transaction() as session:
        session.clear()
    _reset_selected_tables(context.db)


def after_scenario(context, scenario):
    context.db.session.remove()
