from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _NoOpBlueprint:
    def route(self, *_args, **_kwargs):
        def decorator(fn):
            return fn

        return decorator

    def before_request(self, fn):
        return fn


class _IdentitySignal:
    def connect_via(self, *_args, **_kwargs):
        def decorator(fn):
            return fn

        return decorator


def _module(name: str, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _install_import_stubs(monkeypatch):
    flask_admin_helpers = _module("flask_admin.helpers", is_safe_url=lambda *_args, **_kwargs: True)
    monkeypatch.setitem(sys.modules, "flask_admin.helpers", flask_admin_helpers)

    flask_mail = _module("flask_mail", Message=object)
    monkeypatch.setitem(sys.modules, "flask_mail", flask_mail)

    flask_principal = _module(
        "flask_principal",
        Identity=object,
        identity_changed=SimpleNamespace(send=lambda *_args, **_kwargs: None),
        AnonymousIdentity=object,
        identity_loaded=_IdentitySignal(),
        UserNeed=object,
    )
    monkeypatch.setitem(sys.modules, "flask_principal", flask_principal)

    flask_login = _module(
        "flask_login",
        login_user=lambda *_args, **_kwargs: True,
        current_user=SimpleNamespace(is_authenticated=False),
        logout_user=lambda *_args, **_kwargs: None,
        login_required=lambda fn: fn,
    )
    monkeypatch.setitem(sys.modules, "flask_login", flask_login)

    flask_mod = _module(
        "flask",
        render_template=lambda *_args, **_kwargs: "",
        redirect=lambda target: target,
        request=SimpleNamespace(args={}, url="", referrer=None, endpoint=None, args_get=lambda *_a, **_k: None),
        url_for=lambda endpoint, **_kwargs: endpoint,
        flash=lambda *_args, **_kwargs: None,
        abort=lambda code: code,
        session={},
        current_app=SimpleNamespace(config={}, logger=SimpleNamespace(exception=lambda *_a, **_k: None), _get_current_object=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "flask", flask_mod)

    oauth_mod = _module("requests_oauthlib", OAuth2Session=object)
    monkeypatch.setitem(sys.modules, "requests_oauthlib", oauth_mod)

    requests_mod = _module("requests")
    monkeypatch.setitem(sys.modules, "requests", requests_mod)

    class _FakeLineBotApi:
        def __init__(self, *_args, **_kwargs):
            pass

        def push_message(self, *_args, **_kwargs):
            return None

    class _FakeWebhookHandler:
        def __init__(self, *_args, **_kwargs):
            pass

    linebot_mod = _module(
        "app.linebot_compat",
        LineBotApi=_FakeLineBotApi,
        WebhookHandler=_FakeWebhookHandler,
    )
    monkeypatch.setitem(sys.modules, "app.linebot_compat", linebot_mod)

    main_mod = _module(
        "app.main",
        db=SimpleNamespace(session=SimpleNamespace(add=lambda *_a, **_k: None, commit=lambda: None)),
        mail=SimpleNamespace(send=lambda *_a, **_k: None),
        app=SimpleNamespace(
            config={
                "LINE_CLIENT_ID": "",
                "LINE_CLIENT_SECRET": "",
                "LINE_MESSAGE_API_ACCESS_TOKEN": "",
                "LINE_MESSAGE_API_CLIENT_SECRET": "",
            }
        ),
    )
    monkeypatch.setitem(sys.modules, "app.main", main_mod)

    url_utils_mod = _module("app.url_utils", external_url=lambda endpoint: endpoint)
    monkeypatch.setitem(sys.modules, "app.url_utils", url_utils_mod)

    class _StaffAccount:
        query = None

    class _StaffLeaveApprover:
        pass

    staff_models_mod = _module(
        "app.staff.models",
        StaffAccount=_StaffAccount,
        StaffLeaveApprover=_StaffLeaveApprover,
    )
    monkeypatch.setitem(sys.modules, "app.staff.models", staff_models_mod)

    forms_mod = _module(
        "app.auth.forms",
        LoginForm=object,
        ForgotPasswordForm=object,
        ResetPasswordForm=object,
    )
    monkeypatch.setitem(sys.modules, "app.auth.forms", forms_mod)

    auth_pkg = _module("app.auth", authbp=_NoOpBlueprint())
    auth_pkg.__path__ = [str(PROJECT_ROOT / "app" / "auth")]
    monkeypatch.setitem(sys.modules, "app.auth", auth_pkg)

    staff_pkg = _module("app.staff")
    staff_pkg.__path__ = [str(PROJECT_ROOT / "app" / "staff")]
    monkeypatch.setitem(sys.modules, "app.staff", staff_pkg)

    monkeypatch.setitem(sys.modules, "app.main", main_mod)
    monkeypatch.setitem(sys.modules, "app.url_utils", url_utils_mod)
    monkeypatch.setitem(sys.modules, "app.linebot_compat", linebot_mod)
    monkeypatch.setitem(sys.modules, "app.staff.models", staff_models_mod)
    monkeypatch.setitem(sys.modules, "app.auth.forms", forms_mod)
    sys.modules.pop("app.auth.views", None)


@pytest.fixture
def auth_views(monkeypatch):
    _install_import_stubs(monkeypatch)
    return importlib.import_module("app.auth.views")


class _FakeQuery:
    def __init__(self, by_email):
        self.by_email = by_email
        self.calls = []

    def filter_by(self, **kwargs):
        self.calls.append(kwargs)
        email = kwargs.get("email")
        return SimpleNamespace(first=lambda: self.by_email.get(email))


def test_google_email_lookup_prefers_exact_match(auth_views, monkeypatch):
    exact_user = SimpleNamespace(email="jutamas.san@mahidol.ac.th")
    alias_user = SimpleNamespace(email="jutamas.san")
    fake_query = _FakeQuery(
        {
            "jutamas.san@mahidol.ac.th": exact_user,
            "jutamas.san": alias_user,
        }
    )
    monkeypatch.setattr(auth_views.StaffAccount, "query", fake_query, raising=False)

    result = auth_views._get_staff_account_for_google_email("jutamas.san@mahidol.ac.th")

    assert result is exact_user
    assert fake_query.calls == [{"email": "jutamas.san@mahidol.ac.th"}]


def test_google_email_lookup_falls_back_to_local_part(auth_views, monkeypatch):
    alias_user = SimpleNamespace(email="anchanika.kha")
    fake_query = _FakeQuery({"anchanika.kha": alias_user})
    monkeypatch.setattr(auth_views.StaffAccount, "query", fake_query, raising=False)

    result = auth_views._get_staff_account_for_google_email("anchanika.kha@mahidol.ac.th")

    assert result is alias_user
    assert fake_query.calls == [
        {"email": "anchanika.kha@mahidol.ac.th"},
        {"email": "anchanika.kha"},
    ]
