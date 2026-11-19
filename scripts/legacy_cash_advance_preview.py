"""Create a read-only Markdown preview of an old cash-advance XLS report.

This standalone runner loads the parser directly so it does not initialize the
Flask app or connect to a database. It does not mark rows as safe to import.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


PARSER_PATH = (
    Path(__file__).resolve().parents[1]
    / "app" / "advance_payment" / "legacy_xls.py"
)


def _load_parser():
    spec = importlib.util.spec_from_file_location("legacy_xls_preview", PARSER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _money(value):
    return f"{value:,.2f}" if value is not None else "อ่านไม่ได้"


def _cell(value):
    return str(value or "-").replace("|", "\\|").replace("\n", " ")


def _render(report, source_name):
    issues = sum(bool(row.issues) for row in report.rows)
    lines = [
        "# Demo: ตรวจข้อมูลนำเข้าลูกหนี้เงินยืม",
        "",
        f"ไฟล์: `{source_name}`  ",
        f"วันที่รายงาน: {report.report_date or 'อ่านไม่ได้'}  ",
        f"Worksheet: `{report.sheet_name}`  ",
        f"พบ ticket: **{len(report.rows)}** รายการ  ",
        f"ต้องตรวจเพิ่ม: **{issues}** รายการ",
        "",
        "> ผลนี้มาจากการอ่าน XLS เท่านั้น ยังไม่ได้จับคู่ผู้ยืมกับฐานข้อมูล "
        "หรือตรวจเลขที่ยืมซ้ำกับฐานข้อมูล และยังไม่ได้สร้างสัญญา",
        "",
        "## ตรวจยอดกับแถวรวมท้ายไฟล์",
        "",
        "| คอลัมน์ | รวมจาก ticket | รวมในไฟล์ | ผล |",
        "| --- | ---: | ---: | --- |",
    ]
    for col in "FGHIJ":
        calculated = (report.calculated_totals or {}).get(col)
        source = (report.file_totals or {}).get(col)
        verdict = "ตรง" if calculated is not None and calculated == source else "ต้องตรวจ"
        lines.append(
            f"| {col} | {_money(calculated)} | {_money(source)} | {verdict} |"
        )
    lines += [
        "",
        "## รายการจาก XLS",
        "",
        "| แถว | เลขที่ยืม | ผู้ยืม (C+D) | วันที่ยืมที่อ่านได้ | ครบกำหนด | F ยอดยืม | G ส่งใช้ | H คงเหลือ | I เอกสารรอเบิก | J คงเหลือสุทธิ | ผลอ่านไฟล์ |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report.rows:
        status = "; ".join(issue.message for issue in row.issues) or "อ่านได้"
        lines.append(
            "| "
            + " | ".join((
                str(row.source_row),
                _cell(row.ticket_number),
                _cell(row.borrower_name),
                f"{_cell(row.borrow_text)} → {_cell(row.borrow_date)}",
                _cell(row.due_date),
                _money(row.borrowed_amount),
                _money(row.repaid_amount),
                _money(row.balance_before_pending),
                _money(row.pending_documents_amount),
                _money(row.opening_balance_amount),
                _cell(status),
            ))
            + " |"
        )
    if report.issues:
        lines += ["", "## ปัญหาระดับไฟล์", ""]
        lines += [f"- {issue.message}" for issue in report.issues]
    lines += [""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="source .xls report")
    parser.add_argument("--output", type=Path, help="write preview Markdown here")
    args = parser.parse_args()
    legacy_xls = _load_parser()
    try:
        report = legacy_xls.parse_legacy_cash_advance_xls(args.file.read_bytes())
    except (OSError, legacy_xls.LegacyXlsError) as exc:
        parser.exit(2, f"Cannot preview XLS: {exc}\n")
    preview = _render(report, args.file.name)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(preview, encoding="utf-8")
        print(f"Preview: {args.output.resolve()}")
    else:
        print(preview)


if __name__ == "__main__":
    main()
