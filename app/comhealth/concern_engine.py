from __future__ import annotations

import math
import re
import unicodedata
from collections import OrderedDict

from .health_risk_copy import get_health_risk_copy
from .concern_rules import ISSUE_RULES


def _fold_text(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _parse_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(value):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _safe_lower(value):
    return _fold_text(value)


def _alias_in_text(alias, text):
    if not alias or not text:
        return False
    alias = _safe_lower(alias)
    text = _safe_lower(text)
    if not alias or not text:
        return False
    if alias == text:
        return True
    return re.search(r"(?:^|[^a-z0-9]){}(?:$|[^a-z0-9])".format(re.escape(alias)), text) is not None


def _gender_key(gender):
    try:
        gender_int = int(gender)
    except (TypeError, ValueError):
        return "default"
    if gender_int == 1:
        return "male"
    if gender_int == 2:
        return "female"
    return "default"


def _status_label(score, copy):
    if score <= 0:
        return copy["no_concern"]
    if score <= 2:
        return copy["mild"]
    if score <= 4:
        return copy["moderate"]
    return copy["high"]


def _status_badge_class(score):
    if score <= 0:
        return "is-success"
    if score <= 2:
        return "is-dark"
    if score <= 4:
        return "is-warning"
    return "is-danger"


def _evidence_status_to_score(status):
    return {
        "normal": 0,
        "borderline": 1,
        "abnormal": 2,
        "critical": 3,
    }.get(status, 0)


def _format_value(value):
    if value is None or value == "":
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_range(rule):
    if not rule:
        return "-"
    thresholds = rule.get("thresholds") or rule.get("thresholds_by_gender", {}).get("default", {})
    direction = rule.get("direction")
    if direction == "upper":
        return "< {}".format(thresholds.get("borderline", "-"))
    if direction == "lower":
        return ">={}".format(thresholds.get("borderline", "-"))
    if direction == "range":
        return "{} - {}".format(
            thresholds.get("low_borderline", "-"),
            thresholds.get("high_borderline", "-"),
        )
    if direction == "blood_pressure":
        return "< 130/80"
    if direction == "urine_protein":
        return "Negative"
    return "-"


def _match_row(rows, rule):
    aliases = rule.get("aliases", [])
    source = rule.get("source")

    for row in rows:
        tcode = row.get("tcode")
        test_name = row.get("testNamePrintResult") or row.get("testName") or row.get("name")
        if source and row.get("source") == source:
            return row
        if tcode and any(_alias_in_text(alias, tcode) for alias in aliases):
            return row
        if test_name and any(_alias_in_text(alias, test_name) for alias in aliases):
            return row
    return None


def _calculate_bmi(physical):
    weight = _parse_float(physical.get("weight"))
    height = _parse_float(physical.get("height"))
    if not weight or not height:
        return None
    if height <= 0:
        return None
    return round(weight / ((height / 100.0) ** 2), 1)


def _calculate_egfr(creatinine, age, gender):
    try:
        age = int(age)
        creatinine = float(creatinine)
    except (TypeError, ValueError):
        return None

    if age <= 0:
        return None

    gender_key = _gender_key(gender)
    if gender_key == "female":
        base = 144
        ref = 0.7
        factor = -0.329 if creatinine <= 0.7 else -1.209
    elif gender_key == "male":
        base = 141
        ref = 0.9
        factor = -0.411 if creatinine <= 0.9 else -1.209
    else:
        return None

    return round(base * (creatinine / ref) ** factor * (0.993 ** age), 2)


def _normalize_bp(value):
    if not value:
        return None, None
    text = str(value).strip()
    if "/" in text:
        parts = text.split("/", 1)
        try:
            return int(float(parts[0])), int(float(parts[1]))
        except (TypeError, ValueError):
            return None, None
    try:
        systolic = int(float(text))
    except (TypeError, ValueError):
        return None, None
    return systolic, None


def _evaluate_upper(value, thresholds):
    if value is None:
        return "missing"
    if value >= thresholds.get("critical", float("inf")):
        return "critical"
    if value >= thresholds.get("abnormal", float("inf")):
        return "abnormal"
    if value >= thresholds.get("borderline", float("inf")):
        return "borderline"
    return "normal"


def _evaluate_lower(value, thresholds):
    if value is None:
        return "missing"
    if value < thresholds.get("critical", float("-inf")):
        return "critical"
    if value < thresholds.get("abnormal", float("-inf")):
        return "abnormal"
    if value < thresholds.get("borderline", float("-inf")):
        return "borderline"
    return "normal"


def _evaluate_range(value, thresholds):
    if value is None:
        return "missing"
    if value < thresholds.get("low_critical", float("-inf")) or value > thresholds.get("high_critical", float("inf")):
        return "critical"
    if value < thresholds.get("low_abnormal", float("-inf")) or value > thresholds.get("high_abnormal", float("inf")):
        return "abnormal"
    if value < thresholds.get("low_borderline", float("-inf")) or value > thresholds.get("high_borderline", float("inf")):
        return "borderline"
    return "normal"


def _evaluate_blood_pressure(value):
    systolic, diastolic = _normalize_bp(value)
    if systolic is None and diastolic is None:
        return "missing"
    systolic = systolic if systolic is not None else diastolic
    diastolic = diastolic if diastolic is not None else systolic
    if systolic >= 180 or diastolic >= 120:
        return "critical"
    if systolic >= 140 or diastolic >= 90:
        return "abnormal"
    if systolic >= 130 or diastolic >= 80:
        return "borderline"
    if systolic < 90 or diastolic < 60:
        return "borderline"
    return "normal"


def _evaluate_urine_protein(value):
    if value is None:
        return "missing"
    text = _safe_lower(value)
    if not text:
        return "missing"
    if "negative" in text or text in {"nil", "none", "normal"}:
        return "normal"
    if "trace" in text:
        return "borderline"
    if "4+" in text or "+++?" in text:
        return "critical"
    if "3+" in text:
        return "critical"
    if "2+" in text or "1+" in text:
        return "abnormal"
    numeric = _parse_float(value)
    if numeric is None:
        return "abnormal"
    if numeric <= 0:
        return "normal"
    if numeric <= 1:
        return "borderline"
    if numeric <= 2:
        return "abnormal"
    return "critical"


def _evaluate_metric(rule, evidence_value, gender):
    direction = rule.get("direction")
    if direction == "blood_pressure":
        return _evaluate_blood_pressure(evidence_value)
    if direction == "urine_protein":
        return _evaluate_urine_protein(evidence_value)

    thresholds = rule.get("thresholds")
    if "thresholds_by_gender" in rule:
        thresholds = rule["thresholds_by_gender"].get(_gender_key(gender), rule["thresholds_by_gender"].get("default"))

    numeric = _parse_float(evidence_value)
    if direction == "upper":
        return _evaluate_upper(numeric, thresholds or {})
    if direction == "lower":
        return _evaluate_lower(numeric, thresholds or {})
    if direction == "range":
        return _evaluate_range(numeric, thresholds or {})
    return "missing"


def _evidence_from_row(rule, row):
    if not row:
        return None
    return row.get("testResult")


def _build_evidence_item(rule, row, value, gender, copy, derived=False):
    status = _evaluate_metric(rule, value, gender)
    score = _evidence_status_to_score(status)
    if rule.get("role") == "modifier" and status not in {"missing", "normal"}:
        score = max(score, 1)
    if derived and status == "missing":
        score = 0

    return {
        "key": rule["key"],
        "label": copy["evidence_label"].get(rule["key"], rule["label"]),
        "value": _format_value(value if value is not None else "-"),
        "unit": (row or {}).get("unit", "") if row else "",
        "reference_range": (row or {}).get("refBookTh") or _format_range(rule),
        "status": status,
        "score": score,
        "role": rule.get("role", "core"),
        "required": bool(rule.get("required", False)),
        "source": row.get("tcode") if row else rule.get("source", rule["key"]),
        "raw_name": (row or {}).get("testNamePrintResult") or rule["label"],
        "derived": derived,
    }


def _evidence_from_source(rule, rows, physical, age, gender, copy):
    source = rule.get("source")
    if source == "bmi":
        bmi = _calculate_bmi(physical)
        return _build_evidence_item(rule, {"unit": "kg/m2", "refBookTh": "18.5 - 22.9"}, bmi, gender, copy, derived=True)
    if source == "blood_pressure":
        return _build_evidence_item(rule, {"unit": "mmHg", "refBookTh": "< 130/80"}, physical.get("systolic"), gender, copy, derived=True)
    if source == "egfr":
        creatinine_row = _match_row(rows, {"aliases": ["CRE", "CREATININE"]})
        creatinine_value = creatinine_row.get("testResult") if creatinine_row else physical.get("creatinine")
        egfr_value = _calculate_egfr(creatinine_value, age, gender)
        return _build_evidence_item(rule, {"unit": "mL/min/1.73m2", "refBookTh": ">= 90"}, egfr_value, gender, copy, derived=True)
    if source == "triglycerides_hdl_ratio":
        triglycerides_row = _match_row(rows, {"aliases": ["TG", "TRIGLYCERIDE", "TRIGLYCERIDES"]})
        hdl_row = _match_row(rows, {"aliases": ["HDLC", "HDL", "HDL-C", "HDL CHOLESTEROL"]})
        triglycerides_value = _parse_float(triglycerides_row.get("testResult")) if triglycerides_row else None
        hdl_value = _parse_float(hdl_row.get("testResult")) if hdl_row else None
        ratio_value = None
        if triglycerides_value is not None and hdl_value not in (None, 0):
            ratio_value = round(triglycerides_value / hdl_value, 2)
        synthetic_row = {
            "unit": "",
            "refBookTh": "< 2.0",
            "tcode": "TG/HDL",
            "testNamePrintResult": "Triglycerides / HDL ratio",
        }
        return _build_evidence_item(rule, synthetic_row, ratio_value, gender, copy, derived=True)
    return _build_evidence_item(rule, None, None, gender, copy)


def _build_evidence(rule, rows, physical, question, age, gender, copy):
    if rule.get("source"):
        return _evidence_from_source(rule, rows, physical, age, gender, copy)

    row = _match_row(rows, rule)
    if not row:
        return _build_evidence_item(rule, None, None, gender, copy)
    return _build_evidence_item(rule, row, _evidence_from_row(rule, row), gender, copy)


def _score_issue(issue_rule, evidence_items, trigger_severity=0):
    evidence_score = sum(item["score"] for item in evidence_items if item["status"] != "missing")
    return max(evidence_score, trigger_severity)


def _explain_issue(issue_name, score, missing_evidence, evidence_items, copy):
    if score <= 0:
        base = "{}".format(copy["no_concern"])
    elif score <= 2:
        base = "{}".format(copy["mild"])
    elif score <= 4:
        base = "{}".format(copy["moderate"])
    else:
        base = "{}".format(copy["high"])

    notable = [
        "{}: {}".format(item["label"], copy["status"].get(item["status"], item["status"]))
        for item in evidence_items
        if item["status"] in {"borderline", "abnormal", "critical"}
    ]
    if notable:
        base += " {}: {}.".format(copy["supporting_findings"], ", ".join(notable))
    if missing_evidence:
        base += " {}.".format(copy["evidence_incomplete"])
    return base


def build_health_risk_report(rows, physical, question, age, gender, trigger_overrides=None, lang="en"):
    copy = get_health_risk_copy(lang)
    trigger_overrides = trigger_overrides or {}
    issues = []

    for issue_rule in ISSUE_RULES:
        evidence_items = [
            _build_evidence(evidence_rule, rows, physical, question, age, gender, copy)
            for evidence_rule in issue_rule["evidence"]
        ]
        missing_evidence = [
            item["label"]
            for item in evidence_items
            if item["status"] == "missing"
        ]
        score = _score_issue(issue_rule, evidence_items, trigger_overrides.get(issue_rule["key"], 0))
        completeness = round(
            100 * sum(1 for item in evidence_items if item["status"] != "missing") / len(evidence_items),
            0,
        ) if evidence_items else 100
        issue = {
            "key": issue_rule["key"],
            "issue_name": copy["issue_name"].get(issue_rule["key"], issue_rule["name"]),
            "description": copy["description"].get(issue_rule["key"], issue_rule["description"]),
            "concern_score": score,
            "concern_level": _status_label(score, copy),
            "concern_badge_class": _status_badge_class(score),
            "evidence_completeness": int(completeness),
            "supporting_lab_results": [item for item in evidence_items if item["status"] != "missing"],
            "evidence_table": evidence_items,
            "missing_evidence": missing_evidence,
            "short_explanation": _explain_issue(copy["issue_name"].get(issue_rule["key"], issue_rule["name"]), score, missing_evidence, evidence_items, copy),
        }
        issues.append(issue)

    top_issues = sorted(
        issues,
        key=lambda item: (item["concern_score"], item["evidence_completeness"]),
        reverse=True,
    )[:3]

    issues = sorted(
        issues,
        key=lambda item: (item["concern_score"], item["evidence_completeness"]),
        reverse=True,
    )

    return {
        "issues": issues,
        "top_issues": top_issues,
        "issue_count": len(issues),
        "lang": "th" if str(lang).lower().startswith("th") else "en",
    }
