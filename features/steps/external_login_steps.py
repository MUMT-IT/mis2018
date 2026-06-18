from types import SimpleNamespace
from unittest.mock import patch

from behave import given, then, when


class _FakeExternalUser:
    def __init__(self, user_id, email, password):
        self.id = user_id
        self.external_email = email.lower()
        self._password = password
        self.personal_info = SimpleNamespace(
            fullname='External Employee',
            org=SimpleNamespace(
                is_external=True,
                display_name='External Organization',
                name='External Organization',
            ),
        )

    def verify_password(self, password):
        return password == self._password

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class _FakeUsernameQuery:
    def __init__(self, user, calls):
        self._user = user
        self._calls = calls
        self._email = None

    def filter_by(self, **kwargs):
        self._email = kwargs.get('email')
        self._calls.append(('email_lookup', self._email))
        return self

    def first(self):
        return self._user if self._email == _external_username(self._user.external_email) else None


def _external_username(email):
    return (email or '').split('@', 1)[0].lower()


def _patch_external_lookup(context, email, password):
    from app.staff.models import StaffAccount

    context.fake_user = _FakeExternalUser(9001, email, password)
    context.app.config.setdefault('BEHAVE_USER_REGISTRY', {})[str(context.fake_user.id)] = context.fake_user
    context.lookup_calls = []

    lookup_patch = patch.object(
        StaffAccount,
        'get_account_by_external_email',
        side_effect=lambda lookup_email: (
            context.lookup_calls.append(('external_email_lookup', (lookup_email or '').strip().lower()))
            or (context.fake_user if (lookup_email or '').strip().lower() == context.fake_user.external_email else None)
        ),
    )
    lookup_patch.start()
    context.patches.append(lookup_patch)


def _record_username_lookup(context, username):
    import app.auth.views as auth_views

    query_patch = patch.object(
        auth_views.db.session,
        'query',
        side_effect=lambda model: _FakeUsernameQuery(context.fake_user, context.lookup_calls),
    )
    login_patch = patch.object(auth_views, 'login_user', return_value=True)
    identity_patch = patch.object(auth_views.identity_changed, 'send', return_value=None)

    query_patch.start()
    login_patch.start()
    identity_patch.start()
    context.patches.extend([query_patch, login_patch, identity_patch])

    with context.app.test_request_context(
        '/auth/login-external',
        method='POST',
        data={
            'email': username,
            'password': context.fake_user._password,
            'remember_me': 'y',
        },
    ):
        auth_views._handle_password_login(
            SimpleNamespace(
                email=SimpleNamespace(data=username),
                password=SimpleNamespace(data=context.fake_user._password),
                remember_me=SimpleNamespace(data=True),
            ),
            external_only=True,
        )


@given('an external staff account with email "{email}" and password "{password}"')
def step_impl(context, email, password):
    _patch_external_lookup(context, email, password)


@when('I submit the external login form')
def step_impl(context):
    context.lookup_mode = 'external_email'
    response = context.client.post(
        '/auth/login-external',
        data={
            'email': context.fake_user.external_email,
            'password': context.fake_user._password,
            'remember_me': 'y',
        },
        follow_redirects=True,
    )
    context.response = response


@when('I submit the external login form with "{username}" as a username')
def step_impl(context, username):
    import app.auth.views as auth_views

    context.lookup_mode = 'username'

    response = context.client.post(
        '/auth/login-external',
        data={
            'email': username,
            'password': context.fake_user._password,
            'remember_me': 'y',
        },
        follow_redirects=True,
    )
    context.response = response
    _record_username_lookup(context, username)


@then('I should be logged in and directed to the external landing page')
def step_impl(context):
    assert context.response.status_code == 200
    body = context.response.get_data(as_text=True)
    assert 'External Employee Portal' in body
    assert 'External employee access only' in body

    if context.lookup_mode == 'external_email':
        assert ('external_email_lookup', context.fake_user.external_email) in context.lookup_calls, context.lookup_calls
        assert not any(kind == 'email_lookup' for kind, _value in context.lookup_calls), context.lookup_calls
    elif context.lookup_mode == 'username':
        expected_username = _external_username(context.fake_user.external_email)
        assert ('email_lookup', expected_username) in context.lookup_calls, context.lookup_calls
        assert not any(kind == 'external_email_lookup' for kind, _value in context.lookup_calls), context.lookup_calls
    else:
        raise AssertionError('Missing lookup mode')
