from __future__ import annotations

import importlib.util
import os
import sys
import types

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(PROJECT_ROOT, "app")
COMHEALTH_DIR = os.path.join(APP_DIR, "comhealth")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

app_pkg = sys.modules.setdefault("app", types.ModuleType("app"))
app_pkg.__path__ = [APP_DIR]
comhealth_pkg = sys.modules.setdefault("app.comhealth", types.ModuleType("app.comhealth"))
comhealth_pkg.__path__ = [COMHEALTH_DIR]


def _load_module(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_load_module("app.comhealth.concern_rules", os.path.join(COMHEALTH_DIR, "concern_rules.py"))
concern_engine = _load_module("app.comhealth.concern_engine", os.path.join(COMHEALTH_DIR, "concern_engine.py"))
build_health_risk_report = concern_engine.build_health_risk_report
health_risk_summary = _load_module("app.comhealth.health_risk_summary", os.path.join(COMHEALTH_DIR, "health_risk_summary.py"))
build_health_risk_summary = health_risk_summary.build_health_risk_summary


def _row(tcode, name, result, ref, unit):
    return {
        "tcode": tcode,
        "testNamePrintResult": name,
        "testResult": result,
        "refBookTh": ref,
        "unit": unit,
        "testNormalBook": True,
        "isProfile": False,
    }


def _find_issue(report, key):
    for issue in report["issues"]:
        if issue["key"] == key:
            return issue
    raise AssertionError(f"issue not found: {key}")


def test_normal_case_returns_no_current_concern():
    rows = [
        _row("GTT2", "Fasting glucose", "92", "70 - 99", "mg/dL"),
        _row("LDL2", "LDL cholesterol", "88", "< 100", "mg/dL"),
        _row("HDLC", "HDL cholesterol", "52", ">= 40", "mg/dL"),
        _row("TG", "Triglycerides", "110", "< 150", "mg/dL"),
        _row("CHO", "Total cholesterol", "168", "< 200", "mg/dL"),
        _row("BUN", "BUN", "14", "8 - 20", "mg/dL"),
        _row("CRE", "Creatinine", "0.8", "0.6 - 1.3", "mg/dL"),
        _row("AST", "AST", "21", "< 40", "U/L"),
        _row("ALT", "ALT", "18", "< 40", "U/L"),
        _row("ALK", "ALP", "92", "40 - 120", "U/L"),
        _row("UA", "Uric acid", "5.8", "3.5 - 7.2", "mg/dL"),
        _row("CBC11", "Hemoglobin", "14.5", "13.0 - 17.0", "g/dL"),
        _row("CBC12", "Hematocrit", "43", "40 - 50", "%"),
        _row("CBC13", "MCV", "90", "80 - 99", "fL"),
    ]
    report = build_health_risk_report(rows, {"weight": "60", "height": "170", "systolic": "118/76"}, {}, age=40, gender=1)
    assert all(issue["concern_score"] == 0 for issue in report["issues"])
    assert all("No current concern based on available results" in issue["concern_level"] for issue in report["issues"])


def test_borderline_glucose_returns_mild_diabetes_concern():
    report = build_health_risk_report(
        rows=[
            _row("GTT2", "Fasting glucose", "110", "70 - 99", "mg/dL"),
            _row("CRE", "Creatinine", "0.9", "0.6 - 1.3", "mg/dL"),
        ],
        physical={"weight": "60", "height": "170"},
        question={},
        age=40,
        gender=1,
    )
    diabetes = _find_issue(report, "diabetes_risk")
    assert diabetes["concern_score"] == 1
    assert diabetes["concern_level"] == "Mild concern"


def test_high_ldl_plus_high_bmi_increases_cardiovascular_concern():
    report = build_health_risk_report(
        rows=[
            _row("LDL2", "LDL cholesterol", "170", "< 100", "mg/dL"),
            _row("HDLC", "HDL cholesterol", "35", ">= 40", "mg/dL"),
            _row("TG", "Triglycerides", "220", "< 150", "mg/dL"),
            _row("CHO", "Total cholesterol", "168", "< 200", "mg/dL"),
        ],
        physical={"weight": "85", "height": "175", "systolic": "118/76"},
        question={},
        age=40,
        gender=1,
    )
    cardiovascular = _find_issue(report, "cardiovascular_risk")
    assert cardiovascular["concern_score"] >= 3
    assert cardiovascular["concern_level"] in {"Moderate concern", "High concern"}
    ratio_item = next(item for item in cardiovascular["evidence_table"] if item["key"] == "triglycerides_hdl_ratio")
    assert ratio_item["status"] in {"borderline", "abnormal", "critical"}
    assert ratio_item["value"] != "-"


def test_missing_hba1c_appears_as_missing_evidence_not_normal():
    report = build_health_risk_report(
        rows=[
            _row("GTT2", "Fasting glucose", "92", "70 - 99", "mg/dL"),
        ],
        physical={"weight": "60", "height": "170"},
        question={},
        age=40,
        gender=1,
    )
    diabetes = _find_issue(report, "diabetes_risk")
    hba1c_item = next(item for item in diabetes["evidence_table"] if item["key"] == "hba1c")
    assert hba1c_item["status"] == "missing"
    assert "HbA1c" in diabetes["missing_evidence"]


def test_cbc10_rbc_and_cbc13_mcv_are_mapped_correctly():
    report = build_health_risk_report(
        rows=[
            _row("CBC10", "RBC", "5.56", "4.0 - 6.0", "10^6/uL"),
            _row("CBC11", "Hemoglobin", "14.5", "13.0 - 17.0", "g/dL"),
            _row("CBC12", "Hematocrit", "43", "40 - 50", "%"),
            _row("CBC13", "MCV", "90", "80 - 99", "fL"),
        ],
        physical={"weight": "60", "height": "170"},
        question={},
        age=40,
        gender=1,
    )
    anemia = _find_issue(report, "anemia_concern")
    mcv_item = next(item for item in anemia["evidence_table"] if item["key"] == "mcv")
    assert mcv_item["status"] == "normal"
    assert mcv_item["reference_range"] == "80 - 99"
    assert anemia["concern_score"] == 0


def test_one_strongly_abnormal_value_can_raise_concern():
    report = build_health_risk_report(
        rows=[
            _row("UA", "Uric acid", "10.8", "3.5 - 7.2", "mg/dL"),
            _row("CRE", "Creatinine", "1.0", "0.6 - 1.3", "mg/dL"),
        ],
        physical={"weight": "60", "height": "170"},
        question={},
        age=40,
        gender=1,
    )
    gout = _find_issue(report, "gout_risk")
    assert gout["concern_score"] >= 3
    assert gout["concern_level"] in {"Moderate concern", "High concern"}


def test_thai_language_switch_localizes_issue_names():
    report = build_health_risk_report(
        rows=[
            _row("GTT2", "Fasting glucose", "110", "70 - 99", "mg/dL"),
        ],
        physical={"weight": "60", "height": "170"},
        question={},
        age=40,
        gender=1,
        lang="th",
    )
    diabetes = _find_issue(report, "diabetes_risk")
    assert diabetes["issue_name"] == "ความเสี่ยงเบาหวาน"
    assert report["lang"] == "th"


def test_fallback_health_summary_mentions_top_concerns():
    report = build_health_risk_report(
        rows=[
            _row("GTT2", "Fasting glucose", "110", "70 - 99", "mg/dL"),
            _row("LDL2", "LDL cholesterol", "170", "< 100", "mg/dL"),
            _row("HDLC", "HDL cholesterol", "52", ">= 40", "mg/dL"),
        ],
        physical={"weight": "85", "height": "175"},
        question={},
        age=40,
        gender=1,
        lang="en",
    )
    summary = build_health_risk_summary(report, lang="en")
    assert summary["summary_title"] == "What matters most"
    assert summary["top_concerns"]
    assert summary["what_matters"]


def test_issues_are_sorted_by_risk_descending():
    report = build_health_risk_report(
        rows=[
            _row("GTT2", "Fasting glucose", "110", "70 - 99", "mg/dL"),
            _row("LDL2", "LDL cholesterol", "170", "< 100", "mg/dL"),
            _row("UA", "Uric acid", "10.8", "3.5 - 7.2", "mg/dL"),
            _row("CRE", "Creatinine", "1.0", "0.6 - 1.3", "mg/dL"),
        ],
        physical={"weight": "85", "height": "175"},
        question={},
        age=40,
        gender=1,
        lang="en",
    )
    scores = [issue["concern_score"] for issue in report["issues"]]
    assert scores == sorted(scores, reverse=True)


def test_triglyceride_hdl_ratio_is_reported_in_metabolic_section():
    report = build_health_risk_report(
        rows=[
            _row("TG", "Triglycerides", "180", "< 150", "mg/dL"),
            _row("HDLC", "HDL cholesterol", "40", ">= 40", "mg/dL"),
        ],
        physical={"weight": "70", "height": "170"},
        question={},
        age=40,
        gender=1,
        lang="en",
    )
    metabolic = _find_issue(report, "obesity_metabolic_health")
    ratio_item = next(item for item in metabolic["evidence_table"] if item["key"] == "triglycerides_hdl_ratio")
    assert ratio_item["label"] == "Triglycerides / HDL ratio"
    assert ratio_item["status"] != "missing"
