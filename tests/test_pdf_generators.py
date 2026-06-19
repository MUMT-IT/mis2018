from __future__ import annotations

import builtins
import importlib
import io
import os
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from flask import Flask
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _module(name: str, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _install_common_stubs(monkeypatch):
    monkeypatch.setattr(builtins, "os", os, raising=False)

    qrcode = _module(
        "qrcode",
        make=lambda *_args, **_kwargs: SimpleNamespace(save=lambda *_a, **_k: None),
    )
    monkeypatch.setitem(sys.modules, "qrcode", qrcode)

    bahttext = _module("bahttext", bahttext=lambda value: str(value))
    monkeypatch.setitem(sys.modules, "bahttext", bahttext)

    linebot = _module("linebot")
    linebot_exceptions = _module("linebot.exceptions", LineBotApiError=RuntimeError)
    linebot_models = _module("linebot.models", TextSendMessage=object)
    monkeypatch.setitem(sys.modules, "linebot", linebot)
    monkeypatch.setitem(sys.modules, "linebot.exceptions", linebot_exceptions)
    monkeypatch.setitem(sys.modules, "linebot.models", linebot_models)

    flask_mail = _module("flask_mail", Message=object)
    monkeypatch.setitem(sys.modules, "flask_mail", flask_mail)

    flask_principal = _module(
        "flask_principal",
        Identity=object,
        identity_changed=object(),
        AnonymousIdentity=object,
    )
    monkeypatch.setitem(sys.modules, "flask_principal", flask_principal)

    flask_admin = _module("flask_admin")
    flask_admin_helpers = _module("flask_admin.helpers", is_safe_url=lambda *_args, **_kwargs: True)
    monkeypatch.setitem(sys.modules, "flask_admin", flask_admin)
    monkeypatch.setitem(sys.modules, "flask_admin.helpers", flask_admin_helpers)

    auth_views = _module("app.auth.views", line_bot_api=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "app.auth.views", auth_views)

    url_utils = _module("app.url_utils", external_url=lambda *_args, **_kwargs: "")
    monkeypatch.setitem(sys.modules, "app.url_utils", url_utils)

    main = _module(
        "app.main",
        app=Flask("test"),
        get_credential=lambda: None,
        mail=SimpleNamespace(send=lambda *_args, **_kwargs: None),
        csrf=SimpleNamespace(),
        s3=SimpleNamespace(
            put_object=lambda **_kwargs: None,
            delete_object=lambda **_kwargs: None,
            generate_presigned_url=lambda *_args, **_kwargs: "https://example.com/file",
        ),
        S3_BUCKET_NAME="test-bucket",
    )
    monkeypatch.setitem(sys.modules, "app.main", main)

    models = _module("app.models", Holidays=object(), Org=object())
    monkeypatch.setitem(sys.modules, "app.models", models)

    academic_forms = _module("app.academic_services.forms", __all__=[])
    service_admin_forms = _module("app.service_admin.forms", ServiceResultForm=object, __all__=["ServiceResultForm"])
    monkeypatch.setitem(sys.modules, "app.academic_services.forms", academic_forms)
    monkeypatch.setitem(sys.modules, "app.service_admin.forms", service_admin_forms)

    academic_models = _module("app.academic_services.models", __all__=[])
    service_admin_models = _module("app.service_admin.models", __all__=[])
    monkeypatch.setitem(sys.modules, "app.academic_services.models", academic_models)
    monkeypatch.setitem(sys.modules, "app.service_admin.models", service_admin_models)

    room_scheduler_views = _module("app.room_scheduler.views", new_event=lambda *_args, **_kwargs: None)
    monkeypatch.setitem(sys.modules, "app.room_scheduler.views", room_scheduler_views)

    scb_payment_views = _module("app.scb_payment_service.views", generate_qrcode=lambda *_args, **_kwargs: None)
    monkeypatch.setitem(sys.modules, "app.scb_payment_service.views", scb_payment_views)

    e_sign_api = _module("app.e_sign_api", e_sign=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "app.e_sign_api", e_sign_api)

    continue_models = _module(
        "app.continuing_edu.models",
        db=SimpleNamespace(session=SimpleNamespace(add=lambda *_args, **_kwargs: None, commit=lambda: None)),
        CEMemberRegistration=object,
        CEMemberCertificateStatus=object,
        CERegistrationStatus=object,
    )
    monkeypatch.setitem(sys.modules, "app.continuing_edu.models", continue_models)

    continue_status = _module("app.continuing_edu.status_utils", get_certificate_status=lambda **_kwargs: SimpleNamespace(id=7))
    monkeypatch.setitem(sys.modules, "app.continuing_edu.status_utils", continue_status)


def _register_sarabun_family():
    font_path = os.path.join(PROJECT_ROOT, "app", "static", "fonts")
    for font_name, filename in [
        ("Sarabun", "THSarabunNew.ttf"),
        ("SarabunBold", "THSarabunNewBold.ttf"),
        ("SarabunItalic", "THSarabunNewItalic.ttf"),
    ]:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, os.path.join(font_path, filename)))
    pdfmetrics.registerFontFamily(
        "Sarabun",
        normal="Sarabun",
        bold="SarabunBold",
        italic="SarabunItalic",
        boldItalic="SarabunBold",
    )


def _clear_modules(*names):
    for name in names:
        sys.modules.pop(name, None)


def _install_ot_import_stubs(monkeypatch):
    requests_stub = _module("requests", get=lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {}))
    monkeypatch.setitem(sys.modules, "requests", requests_stub)

    main = _module(
        "app.main",
        app=Flask("test"),
        db=SimpleNamespace(session=None),
        func=SimpleNamespace(timezone=lambda *_args, **_kwargs: SimpleNamespace()),
        StaffPersonalInfo=object(),
        StaffSpecialGroup=object(),
        StaffShiftSchedule=object(),
        StaffWorkLogin=object(),
        StaffLeaveRequest=object(),
    )
    monkeypatch.setitem(sys.modules, "app.main", main)

    models = _module("app.models", Org=object())
    monkeypatch.setitem(sys.modules, "app.models", models)

    forms = _module(
        "app.ot.forms",
        pytz=__import__("pytz"),
        OtPaymentAnnounceForm=object,
        OtCompensationRateForm=object,
        OtTimeSlotForm=object,
        OtDocumentApprovalForm=object,
        DateTimeRange=lambda lower=None, upper=None, bounds=None: SimpleNamespace(lower=lower, upper=upper, bounds=bounds),
        time_slots=[],
        create_ot_record_form=lambda *_args, **_kwargs: object,
        OtScheduleItemForm=object,
        OtScheduleForm=object,
    )
    monkeypatch.setitem(sys.modules, "app.ot.forms", forms)

    roles = _module(
        "app.roles",
        secretary_permission=SimpleNamespace(union=lambda _other: SimpleNamespace(require=lambda: (lambda fn: fn))),
        manager_permission=SimpleNamespace(union=lambda _other: SimpleNamespace(require=lambda: (lambda fn: fn))),
    )
    monkeypatch.setitem(sys.modules, "app.roles", roles)

    auth = _module(
        "pydrive.auth",
        ServiceAccountCredentials=type(
            "FakeServiceAccountCredentials",
            (),
            {"from_json_keyfile_dict": classmethod(lambda cls, *_args, **_kwargs: object())},
        ),
        GoogleAuth=type("FakeGoogleAuth", (), {"__init__": lambda self, *_args, **_kwargs: setattr(self, "credentials", None)}),
    )
    monkeypatch.setitem(sys.modules, "pydrive.auth", auth)

    drive = _module(
        "pydrive.drive",
        GoogleDrive=type("FakeGoogleDrive", (), {"__init__": lambda self, *_args, **_kwargs: None}),
    )
    monkeypatch.setitem(sys.modules, "pydrive.drive", drive)

    _clear_modules("app.ot.views")


def _import_pdf_module(monkeypatch, package_name: str):
    _install_common_stubs(monkeypatch)
    _clear_modules(
        f"app.{package_name}",
        f"app.{package_name}.views",
    )
    views = importlib.import_module(f"app.{package_name}.views")
    _register_sarabun_family()
    return views


def _make_request_payload():
    return [
        {"type": "header", "data": "รายการทดสอบ"},
        {"type": "content_header", "data": "ตรวจวิเคราะห์ตัวอย่าง"},
        {"type": "text", "data": "Sample number: A1, A2<br/>Notes"},
        {"type": "table", "data": [{"Test": "Alpha", "Result": "Positive"}]},
        {"type": "header", "data": "ข้อมูลผลิตภัณฑ์"},
        {"type": "text", "data": "Product: Serum"},
        {"type": "table", "data": [{"Product": "Serum", "Lot": "L-01"}]},
        {"type": "bool", "data": "Accepted"},
    ]


def _make_service_request(code: str):
    return SimpleNamespace(
        sub_lab=SimpleNamespace(code=code, lab_information="123 Lab Road"),
        request_no="REQ-001",
        customer=SimpleNamespace(
            customer_name="Acme Co.",
            customer_info=SimpleNamespace(taxpayer_identification_no="1234567890"),
            contact_phone_number="0123456789",
            contact_email="acme@example.com",
        ),
        receive_name="Receiving Desk",
        receive_address="456 Delivery St.",
        receive_phone_number="0987654321",
        quotation_name="Acme Billing",
        quotation_issue_address="789 Invoice Ave.",
        taxpayer_identification_no="1234567890",
        quotation_phone_number="0123456789",
        report_languages=[SimpleNamespace(report_language=SimpleNamespace(item="Thai"))],
        report_receive_channel=SimpleNamespace(item="Email"),
        samples=[],
    )


def _make_quotation(sign: bool = False):
    approved_at = datetime(2026, 6, 19, 8, 30, tzinfo=timezone.utc)
    return SimpleNamespace(
        quotation_no="QT-001",
        approved_at=approved_at,
        request=SimpleNamespace(sub_lab=SimpleNamespace(lab=SimpleNamespace(lab="Lab A"))),
        name="Acme Co.",
        address="123 Main St.",
        taxpayer_identification_no="1234567890",
        quotation_items=[
            SimpleNamespace(sequence=2, item="<i>Beta</i>", quantity=1, unit_price=20.0, total_price=20.0),
            SimpleNamespace(sequence=1, item="Alpha", quantity=2, unit_price=10.0, total_price=20.0),
        ],
        approver=SimpleNamespace(fullname="Dr. Approver"),
        subtotal=lambda: 40.0,
        grand_total=lambda: 40.0,
        discount=lambda: 0.0,
    )


def _assert_pdf_buffer(buffer):
    assert isinstance(buffer, io.BytesIO)
    data = buffer.getvalue()
    assert data[:4] == b"%PDF"
    assert len(data) > 100


@pytest.fixture
def academic_views(monkeypatch):
    views = _import_pdf_module(monkeypatch, "academic_services")
    views.request_data_paths = {
        "bacteria": lambda *_args, **_kwargs: _make_request_payload(),
        "disinfection": lambda *_args, **_kwargs: _make_request_payload(),
        "air_disinfection": lambda *_args, **_kwargs: _make_request_payload(),
    }
    return views


@pytest.fixture
def service_admin_views(monkeypatch):
    views = _import_pdf_module(monkeypatch, "service_admin")
    views.request_data_paths = {
        "bacteria": lambda *_args, **_kwargs: _make_request_payload(),
        "disinfection": lambda *_args, **_kwargs: _make_request_payload(),
        "air_disinfection": lambda *_args, **_kwargs: _make_request_payload(),
    }
    return views


@pytest.fixture
def ot_views(monkeypatch):
    _install_ot_import_stubs(monkeypatch)
    views = importlib.import_module("app.ot.views")
    monkeypatch.setattr(views, "_is_external_account", lambda: False)
    _register_sarabun_family()
    return views


@pytest.fixture
def certificate_utils(monkeypatch):
    _install_common_stubs(monkeypatch)
    continue_pkg = _module("app.continuing_edu")
    continue_pkg.__path__ = [os.path.join(PROJECT_ROOT, "app", "continuing_edu")]
    continue_pkg.ce_bp = SimpleNamespace()
    continue_pkg.translations = {}
    monkeypatch.setitem(sys.modules, "app.continuing_edu", continue_pkg)
    _clear_modules("app.continuing_edu.certificate_utils")
    return importlib.import_module("app.continuing_edu.certificate_utils")


@pytest.mark.parametrize(
    "module_fixture,function_name,code",
    [
        ("academic_views", "generate_bacteria_request_pdf", "bacteria"),
        ("academic_views", "generate_virus_request_pdf", "disinfection"),
        ("service_admin_views", "generate_bacteria_request_pdf", "bacteria"),
        ("service_admin_views", "generate_virus_request_pdf", "disinfection"),
    ],
)
def test_request_pdf_generators_return_pdf_buffers(request, module_fixture, function_name, code):
    views = request.getfixturevalue(module_fixture)
    buffer = getattr(views, function_name)(_make_service_request(code))
    _assert_pdf_buffer(buffer)


@pytest.mark.parametrize("module_fixture", ["academic_views", "service_admin_views"])
def test_quotation_pdf_generators_return_pdf_buffers(request, module_fixture):
    views = request.getfixturevalue(module_fixture)
    buffer = views.generate_quotation_pdf(_make_quotation(sign=False), sign=False)
    _assert_pdf_buffer(buffer)


@pytest.mark.parametrize("module_fixture", ["academic_views", "service_admin_views"])
def test_quotation_pdf_generators_support_signature_mode(request, module_fixture):
    views = request.getfixturevalue(module_fixture)
    buffer = views.generate_quotation_pdf(_make_quotation(sign=True), sign=True)
    _assert_pdf_buffer(buffer)


def test_ot_finance_pdf_generator_returns_pdf_buffer(ot_views):
    frame = pd.DataFrame(
        [
            {
                "fullname": "Alice",
                "sap": "1001",
                "position": "Technician",
                "rate": 120.0,
                "start": "08:00",
                "end": "17:00",
                "checkins": "08:02",
                "checkouts": "17:01",
                "work_minutes": 540,
                "payment": 1080.0,
            },
            {
                "fullname": "Bob",
                "sap": "1002",
                "position": "Technician",
                "rate": 150.0,
                "start": "08:00",
                "end": "17:00",
                "checkins": "08:00",
                "checkouts": "17:00",
                "work_minutes": 540,
                "payment": 1350.0,
            },
        ]
    )
    buffer = ot_views.build_finance_pdf(frame, datetime(2026, 6, 1, tzinfo=timezone.utc), datetime(2026, 6, 19, tzinfo=timezone.utc))
    _assert_pdf_buffer(buffer)


def test_issue_certificate_generates_pdf_and_updates_registration(certificate_utils, monkeypatch):
    issued = SimpleNamespace(id=99)
    reg = SimpleNamespace(
        member_id=10,
        event_entity_id=20,
        member=SimpleNamespace(payments=[]),
        event_entity=SimpleNamespace(),
        certificate_url=None,
        certificate_status_id=None,
        certificate_issued_date=None,
    )

    calls = {}

    def fake_render_template(template_name, **context):
        calls["template"] = template_name
        calls["context"] = context
        return "<html><body>certificate</body></html>"

    class FakeHTML:
        def __init__(self, *, string, base_url):
            calls["html_string"] = string
            calls["base_url"] = base_url

        def write_pdf(self):
            return b"%PDF-1.4\n% test certificate\n"

    certificate_utils.render_template = fake_render_template
    certificate_utils.HTML = FakeHTML
    certificate_utils.ensure_certificate_status = lambda *_args, **_kwargs: issued
    certificate_utils._delete_certificate_file = lambda *_args, **_kwargs: None
    certificate_utils.db = SimpleNamespace(session=SimpleNamespace(add=lambda *_args, **_kwargs: None, commit=lambda: None))
    monkeypatch.setenv("CE_CERT_STORAGE", "s3")
    monkeypatch.setenv("BUCKETEER_BUCKET_NAME", "test-bucket")

    main = sys.modules["app.main"]
    uploads = []

    def fake_put_object(**kwargs):
        uploads.append(kwargs)

    main.s3 = SimpleNamespace(put_object=fake_put_object)

    result = certificate_utils.issue_certificate(reg, base_url="https://example.com/")

    assert result is reg
    assert reg.certificate_status_id == issued.id
    assert reg.certificate_issued_date is not None
    assert reg.certificate_url == uploads[0]["Key"]
    assert calls["template"] == "continueing_edu/certificate_pdf.html"
    assert calls["base_url"] == "https://example.com/"
    assert uploads and uploads[0]["Bucket"] == "test-bucket"
    assert uploads[0]["ContentType"] == "application/pdf"
