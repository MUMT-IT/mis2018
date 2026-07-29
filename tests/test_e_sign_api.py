from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _module(name: str, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _install_import_stubs(monkeypatch):
    main = _module("app.main", db=SimpleNamespace(session=SimpleNamespace(add=lambda *_a, **_k: None, commit=lambda: None)))
    monkeypatch.setitem(sys.modules, "app.main", main)

    staff_models = _module("app.staff.models", StaffAccount=object())
    monkeypatch.setitem(sys.modules, "app.staff.models", staff_models)

    forms = _module(
        "app.e_sign_api.forms",
        CertificateFileForm=object,
        TestPdfSignForm=object,
    )
    monkeypatch.setitem(sys.modules, "app.e_sign_api.forms", forms)

    models = _module("app.e_sign_api.models", CertificateFile=object)
    monkeypatch.setitem(sys.modules, "app.e_sign_api.models", models)

    class FakeTextStampStyle:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    pyhanko_stamp = _module("pyhanko.stamp", TextStampStyle=FakeTextStampStyle)
    monkeypatch.setitem(sys.modules, "pyhanko.stamp", pyhanko_stamp)

    pyhanko_font = _module(
        "pyhanko.pdf_utils.font.opentype",
        GlyphAccumulatorFactory=lambda path: ("glyph", path),
    )
    monkeypatch.setitem(sys.modules, "pyhanko.pdf_utils.font.opentype", pyhanko_font)

    pyhanko_images = _module("pyhanko.pdf_utils.images", PdfImage=lambda path: ("image", path))
    monkeypatch.setitem(sys.modules, "pyhanko.pdf_utils.images", pyhanko_images)

    pyhanko_text = _module("pyhanko.pdf_utils.text", TextBoxStyle=lambda **kwargs: ("textbox", kwargs))
    monkeypatch.setitem(sys.modules, "pyhanko.pdf_utils.text", pyhanko_text)

    class FakeIncrementalPdfFileWriter:
        def __init__(self, doc, strict=False):
            self.doc = doc
            self.strict = strict

    pyhanko_writer = _module("pyhanko.pdf_utils.incremental_writer", IncrementalPdfFileWriter=FakeIncrementalPdfFileWriter)
    monkeypatch.setitem(sys.modules, "pyhanko.pdf_utils.incremental_writer", pyhanko_writer)

    class FakePdfSignatureMetadata:
        def __init__(self, field_name):
            self.field_name = field_name

    class FakeSimpleSigner:
        called_with = None

        @classmethod
        def load_pkcs12(cls, pfx_file, passphrase):
            cls.called_with = {"pfx_file": pfx_file, "passphrase": passphrase}
            return SimpleNamespace(pfx_file=pfx_file, passphrase=passphrase)

    class FakePdfSigner:
        instances = []

        def __init__(self, signer, signature_meta, stamp_style=None):
            self.signer = signer
            self.signature_meta = signature_meta
            self.stamp_style = stamp_style
            self.background = None
            self.sign_calls = []
            FakePdfSigner.instances.append(self)

        def sign_pdf(self, writer):
            self.sign_calls.append(writer)
            return SimpleNamespace(writer=writer, signer=self.signer, signature_meta=self.signature_meta, background=self.background)

    pyhanko_signers = _module(
        "pyhanko.sign.signers",
        PdfSignatureMetadata=FakePdfSignatureMetadata,
        SimpleSigner=FakeSimpleSigner,
        PdfSigner=FakePdfSigner,
    )
    monkeypatch.setitem(sys.modules, "pyhanko.sign.signers", pyhanko_signers)

    class FakeSigFieldSpec:
        def __init__(self, sig_field_name, on_page, box):
            self.sig_field_name = sig_field_name
            self.on_page = on_page
            self.box = box

    field_calls = []

    def fake_append_signature_field(writer, spec):
        field_calls.append((writer, spec))

    pyhanko_fields = _module(
        "pyhanko.sign.fields",
        SigFieldSpec=FakeSigFieldSpec,
        append_signature_field=fake_append_signature_field,
    )
    monkeypatch.setitem(sys.modules, "pyhanko.sign.fields", pyhanko_fields)

    pyhanko_sign = _module("pyhanko.sign", signers=pyhanko_signers)
    monkeypatch.setitem(sys.modules, "pyhanko.sign", pyhanko_sign)

    pyhanko_pdf_utils = _module(
        "pyhanko.pdf_utils",
        images=pyhanko_images,
        text=pyhanko_text,
    )
    monkeypatch.setitem(sys.modules, "pyhanko.pdf_utils", pyhanko_pdf_utils)

    pyhanko_font_pkg = _module("pyhanko.pdf_utils.font", opentype=pyhanko_font)
    monkeypatch.setitem(sys.modules, "pyhanko.pdf_utils.font", pyhanko_font_pkg)

    pyhanko_pkg = _module("pyhanko", stamp=pyhanko_stamp)
    monkeypatch.setitem(sys.modules, "pyhanko", pyhanko_pkg)

    pkg = _module("app.e_sign_api", esign=SimpleNamespace(route=lambda *_a, **_k: (lambda fn: fn)))
    pkg.__path__ = [str(PROJECT_ROOT / "app" / "e_sign_api")]
    monkeypatch.setitem(sys.modules, "app.e_sign_api", pkg)

    sys.modules.pop("app.e_sign_api.views", None)
    return SimpleNamespace(
        FakePdfSigner=FakePdfSigner,
        FakeSimpleSigner=FakeSimpleSigner,
        field_calls=field_calls,
    )


@pytest.fixture
def e_sign_views(monkeypatch):
    stubs = _install_import_stubs(monkeypatch)
    views = importlib.import_module("app.e_sign_api.views")
    return SimpleNamespace(views=views, stubs=stubs)


def _make_user(include_image=True):
    return SimpleNamespace(
        email="alice@example.com",
        digital_cert_file=SimpleNamespace(
            file=b"pfx-bytes",
            image=b"sig-bytes" if include_image else None,
        ),
    )


def test_e_sign_writes_signature_artifacts_and_sets_background(e_sign_views, monkeypatch, tmp_path):
    views = e_sign_views.views
    stubs = e_sign_views.stubs
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(views, "current_user", _make_user(include_image=True))

    out = views.e_sign(
        doc=SimpleNamespace(name="input.pdf"),
        passphrase="secret",
        x1=10,
        y1=20,
        x2=30,
        y2=40,
        include_image=True,
        sig_field_name="Signature",
        message="Signed by QA",
    )

    assert out.signer.passphrase == b"secret"
    assert out.background == ("image", "alice@example.com_sig.png")
    assert stubs.FakeSimpleSigner.called_with == {
        "pfx_file": "alice@example.com_cert.pfx",
        "passphrase": b"secret",
    }
    assert stubs.field_calls[0][1].box == (10, 20, 30, 40)
    assert Path("alice@example.com_cert.pfx").read_bytes() == b"pfx-bytes"
    assert Path("alice@example.com_sig.png").read_bytes() == b"sig-bytes"
    assert out.writer.doc.name == "input.pdf"
    assert out.writer.strict is False


def test_e_sign_skips_background_when_image_disabled(e_sign_views, monkeypatch, tmp_path):
    views = e_sign_views.views
    stubs = e_sign_views.stubs
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(views, "current_user", _make_user(include_image=True))

    out = views.e_sign(
        doc=SimpleNamespace(name="input.pdf"),
        passphrase="secret",
        include_image=False,
        sig_field_name="ReviewSignature",
    )

    assert out.background is None
    assert stubs.FakeSimpleSigner.called_with["pfx_file"] == "alice@example.com_cert.pfx"
    assert Path("alice@example.com_cert.pfx").exists()
    assert not Path("alice@example.com_sig.png").exists()
    assert stubs.field_calls[0][1].sig_field_name == "ReviewSignature"
