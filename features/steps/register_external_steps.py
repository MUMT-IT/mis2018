import importlib
import importlib.util
import sys
import types
from datetime import datetime
from types import SimpleNamespace
from pathlib import Path

from flask import Blueprint
from behave import given, then, when


class _FakeQuery:
    def __init__(self, *, items=None, getter=None):
        self._items = list(items or [])
        self._getter = getter

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None

    def get(self, value):
        if self._getter:
            return self._getter(value)
        return None

    def filter_by(self, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self


class _FakeSession:
    def __init__(self, registry):
        self._registry = registry
        self._pending = []
        self._next_id = 1

    def add(self, obj):
        self._pending.append(obj)

    def commit(self):
        for obj in self._pending:
            if hasattr(obj, "id") and getattr(obj, "id", None) in (None, 0):
                obj.id = self._next_id
                self._next_id += 1
            if isinstance(obj, _FakeStaffPersonalInfo):
                self._registry["personal_infos"][obj.id] = obj
            if isinstance(obj, _FakeStaffAccount):
                self._registry["accounts"][obj.id] = obj
        self._pending.clear()


class _FakeStaffPersonalInfo:
    query = _FakeQuery()

    def __init__(self, **kwargs):
        self.id = None
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeStaffAccount:
    query = _FakeQuery()

    def __init__(self, **kwargs):
        self.id = None
        self.personal_id = kwargs.get("personal_id")
        self.email = kwargs.get("email")


class _FakeStaffLeaveType:
    query = _FakeQuery(items=[])


class _FakeStaffLeaveQuota:
    query = _FakeQuery()


class _FakeStaffLeaveUsedQuota:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeOrg:
    query = _FakeQuery()

    def __init__(self, *, is_external=False):
        self.is_external = is_external


class _FakeCSRF:
    def exempt(self, fn):
        return fn


def _ensure_import_stubs(context):
    registry = context.app.config.setdefault(
        "BEHAVE_REGISTER_EXTERNAL_REGISTRY",
        {"personal_infos": {}, "accounts": {}},
    )

    app_pkg = sys.modules.get("app")
    if app_pkg is None:
        app_pkg = types.ModuleType("app")
        sys.modules["app"] = app_pkg
    app_pkg.__path__ = [str(Path(__file__).resolve().parents[2] / "app")]

    staff_pkg = sys.modules.get("app.staff")
    if staff_pkg is None:
        staff_pkg = types.ModuleType("app.staff")
        staff_pkg.__path__ = [str(Path(__file__).resolve().parents[2] / "app" / "staff")]
        sys.modules["app.staff"] = staff_pkg
    staff_pkg.__path__ = [str(Path(__file__).resolve().parents[2] / "app" / "staff")]
    if not hasattr(staff_pkg, "staffbp"):
        staff_pkg.staffbp = Blueprint("staff", "app.staff")

    main_mod = sys.modules.get("app.main")
    if main_mod is None:
        main_mod = types.ModuleType("app.main")
        sys.modules["app.main"] = main_mod
    main_mod.app = context.app
    main_mod.db = SimpleNamespace(session=_FakeSession(registry))
    main_mod.mail = getattr(main_mod, "mail", SimpleNamespace(send=lambda *_args, **_kwargs: None))
    main_mod.get_weekdays = getattr(main_mod, "get_weekdays", lambda *_args, **_kwargs: 0)
    main_mod.csrf = getattr(main_mod, "csrf", _FakeCSRF())

    app_models = sys.modules.get("app.models")
    if app_models is None:
        app_models = types.ModuleType("app.models")
        sys.modules["app.models"] = app_models
    app_models.Holidays = getattr(app_models, "Holidays", object)

    staff_forms = sys.modules.get("app.staff.forms")
    if staff_forms is None:
        staff_forms = types.ModuleType("app.staff.forms")
        sys.modules["app.staff.forms"] = staff_forms
    staff_forms.StaffSeminarForm = getattr(staff_forms, "StaffSeminarForm", object)
    staff_forms.create_seminar_attend_form = getattr(staff_forms, "create_seminar_attend_form", object)
    staff_forms.StaffGroupDetailForm = getattr(staff_forms, "StaffGroupDetailForm", object)

    eduqa_models = sys.modules.get("app.eduqa.models")
    if eduqa_models is None:
        eduqa_models = types.ModuleType("app.eduqa.models")
        sys.modules["app.eduqa.models"] = eduqa_models
    eduqa_models.EduQAInstructor = getattr(eduqa_models, "EduQAInstructor", object)

    url_utils = sys.modules.get("app.url_utils")
    if url_utils is None:
        url_utils = types.ModuleType("app.url_utils")
        sys.modules["app.url_utils"] = url_utils
    url_utils.external_url = getattr(url_utils, "external_url", lambda endpoint, **_kwargs: f"/{endpoint}")

    comhealth_views = sys.modules.get("app.comhealth.views")
    if comhealth_views is None:
        comhealth_views = types.ModuleType("app.comhealth.views")
        sys.modules["app.comhealth.views"] = comhealth_views
    comhealth_views.allowed_file = getattr(comhealth_views, "allowed_file", lambda *_args, **_kwargs: True)

    auth_views = sys.modules.get("app.auth.views")
    if auth_views is None:
        auth_views = types.ModuleType("app.auth.views")
        sys.modules["app.auth.views"] = auth_views
    auth_views.line_bot_api = getattr(auth_views, "line_bot_api", object())
    auth_views._normalize_staff_email = getattr(
        auth_views,
        "_normalize_staff_email",
        lambda email: (email or "").strip().lower(),
    )

    staff_models = sys.modules.get("app.staff.models")
    if staff_models is None:
        staff_models = types.ModuleType("app.staff.models")
        sys.modules["app.staff.models"] = staff_models
    if not hasattr(staff_models, "Role"):
        class Role:
            query = _FakeQuery(items=[])

            def to_tuple(self):
                return None

        staff_models.Role = Role
    staff_models.StaffPersonalInfo = getattr(staff_models, "StaffPersonalInfo", _FakeStaffPersonalInfo)
    staff_models.StaffAccount = getattr(staff_models, "StaffAccount", _FakeStaffAccount)
    staff_models.StaffLeaveType = getattr(staff_models, "StaffLeaveType", _FakeStaffLeaveType)
    staff_models.StaffLeaveQuota = getattr(staff_models, "StaffLeaveQuota", _FakeStaffLeaveQuota)
    staff_models.StaffLeaveUsedQuota = getattr(staff_models, "StaffLeaveUsedQuota", _FakeStaffLeaveUsedQuota)
    staff_models.StaffEmployment = getattr(staff_models, "StaffEmployment", object)
    staff_models.StaffJobPosition = getattr(staff_models, "StaffJobPosition", object)
    staff_models.Org = getattr(staff_models, "Org", _FakeOrg)
    staff_models.StaffResignation = getattr(staff_models, "StaffResignation", object)

    linebot_exceptions = types.ModuleType("linebot.exceptions")
    linebot_exceptions.LineBotApiError = Exception
    sys.modules["linebot.exceptions"] = linebot_exceptions

    linebot_models = types.ModuleType("linebot.models")
    linebot_models.TextSendMessage = object
    sys.modules["linebot.models"] = linebot_models

    gviz_api = types.ModuleType("gviz_api")
    gviz_api.DataTable = object
    sys.modules["gviz_api"] = gviz_api

    flask_mail = types.ModuleType("flask_mail")
    sys.modules["flask_mail"] = flask_mail
    flask_mail.Message = getattr(flask_mail, "Message", lambda **kwargs: SimpleNamespace(**kwargs))

    flask_admin = types.ModuleType("flask_admin")
    sys.modules["flask_admin"] = flask_admin
    flask_admin.BaseView = getattr(flask_admin, "BaseView", object)
    flask_admin.expose = getattr(flask_admin, "expose", lambda *args, **_kwargs: (lambda wrapped: wrapped))

    pydrive_auth = types.ModuleType("pydrive.auth")
    sys.modules["pydrive.auth"] = pydrive_auth

    class _GoogleAuth:
        def __init__(self, *_args, **_kwargs):
            self.credentials = None

    class _ServiceAccountCredentials:
        @classmethod
        def from_json_keyfile_dict(cls, *_args, **_kwargs):
            return object()

    pydrive_auth.GoogleAuth = getattr(pydrive_auth, "GoogleAuth", _GoogleAuth)
    pydrive_auth.ServiceAccountCredentials = getattr(
        pydrive_auth,
        "ServiceAccountCredentials",
        _ServiceAccountCredentials,
    )

    pydrive_drive = types.ModuleType("pydrive.drive")
    sys.modules["pydrive.drive"] = pydrive_drive
    pydrive_drive.GoogleDrive = getattr(pydrive_drive, "GoogleDrive", lambda *_args, **_kwargs: object())

    requests_mod = types.ModuleType("requests")
    requests_mod.get = lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {})
    sys.modules["requests"] = requests_mod

    sys.modules.pop("app.staff.views", None)


def _unwrap(view):
    while hasattr(view, "__wrapped__"):
        view = view.__wrapped__
    return view


@given(u'a staff account belongs to external organization')
def step_impl(context):
    context.external_staff_email = "external.employee@example.com"


@when(u'an HR submit the staff account form')
def step_impl(context):
    _ensure_import_stubs(context)
    views_path = Path(__file__).resolve().parents[2] / "app" / "staff" / "views.py"
    spec = importlib.util.spec_from_file_location("app.staff.views", views_path)
    views = importlib.util.module_from_spec(spec)
    sys.modules["app.staff.views"] = views
    spec.loader.exec_module(views)

    registry = context.app.config["BEHAVE_REGISTER_EXTERNAL_REGISTRY"]
    views.db = SimpleNamespace(session=_FakeSession(registry))
    views.StaffAccount = _FakeStaffAccount
    views.StaffPersonalInfo = _FakeStaffPersonalInfo
    views.StaffLeaveType = _FakeStaffLeaveType
    views.StaffLeaveQuota = _FakeStaffLeaveQuota
    views.StaffLeaveUsedQuota = _FakeStaffLeaveUsedQuota
    views.StaffEmployment = object
    views.StaffJobPosition = object
    views.Org = _FakeOrg
    views.StaffResignation = object
    views.render_template = lambda template, **_kwargs: f"rendered:{template}"
    views.url_for = lambda endpoint, **kwargs: (
        f"/for-hr/staff-info/search-account/edit-pwd/{kwargs['staff_id']}"
        if endpoint == "staff.staff_edit_pwd"
        else f"/{endpoint}"
    )

    external_org = _FakeOrg(is_external=True)
    views.Org.query = _FakeQuery(getter=lambda org_id: external_org if org_id == 1 else None)

    form_data = {
        "email": context.external_staff_email,
        "th_title": "นางสาว",
        "th_firstname": "ทดสอบ",
        "th_lastname": "บุคลากร",
        "en_firstname": "Test",
        "en_lastname": "Staff",
        "position": "Officer",
        "employed_date": "01/01/2024",
        "finger_scan_id": "12345",
        "sap_id": "SAP001",
        "employment_id": "1",
        "job_id": "1",
        "org_id": "1",
    }

    with context.app.test_request_context("/for-hr/staff-info/create", method="POST", data=form_data):
        context.response = _unwrap(views.staff_create_info)()


@then(u"the HR should be directed to the HR's staff edit password page")
def step_impl(context):
    assert context.response.status_code == 302
    assert context.response.headers["Location"] == "/for-hr/staff-info/search-account/edit-pwd/2"
