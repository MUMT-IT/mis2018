"""Status labels must remain editable without changing workflow behavior."""

import ast
import re
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _load_status_helpers():
    source = (ROOT / "app/advance_payment/models.py").read_text(encoding="utf-8-sig")
    module = ast.parse(source)
    names = {"status_value_for_record", "status_name_for_record", "status_code_for_record"}
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in names]
    context = {
        "object_session": lambda _record: None,
        "db": SimpleNamespace(session=None),
        "_session_get": lambda *_args: None,
        "AdvancePaymentStatus": object,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), "models.py", "exec"), context)
    return context


def test_status_label_can_change_without_changing_workflow_code():
    helpers = _load_status_helpers()
    status = SimpleNamespace(id=7, code="PENDING", name="ข้อความใหม่")
    record = SimpleNamespace(status_id=7, status_ref=status)

    assert helpers["status_name_for_record"](record) == "ข้อความใหม่"
    assert helpers["status_code_for_record"](record) == "PENDING"

    status.name = "เปลี่ยนคำอีกครั้ง"
    assert helpers["status_name_for_record"](record) == "เปลี่ยนคำอีกครั้ง"
    assert helpers["status_code_for_record"](record) == "PENDING"


def test_templates_do_not_branch_on_status_labels():
    pattern = re.compile(r"\.status(?:\|lower)?\s*(?:==|!=|\bin\b|\bnot\s+in\b)")
    offenders = []
    for path in (ROOT / "app/templates/advance_payment").rglob("*.html"):
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if "{%" in line and pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{line_number}")

    assert offenders == []


def test_badge_colors_are_selected_by_code_only():
    base = (ROOT / "app/templates/advance_payment/base.html").read_text(encoding="utf-8-sig")

    assert "macro status_badge_class(code)" in base
    assert "status_colors" not in base
