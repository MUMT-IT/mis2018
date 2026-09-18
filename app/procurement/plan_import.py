# -*- coding: utf-8 -*-
"""Parse the annual procurement-plan workbook into application-ready rows."""

import re
from decimal import Decimal, InvalidOperation

import pandas as pd


DATA_SHEET = u'กรอกข้อมูล'

REQUIRED_COLUMNS = {
    'item': u'Long Text',
    'product_code': u'ผลผลิต/โครงการ/รายงาน (Functional Area)',
    'cost_center': u'หน่วยงานที่รับผิดชอบ (Cost center)',
    'procurement_method': u'วิธีการจัดซื้อจัดจ้าง (แผน)',
    'amount': u'จำนวนเงิน',
    'funding_source': u'Fund',
}

OPTIONAL_COLUMNS = {
    'external_order_no': u'External order no.',
}


class ProcurementPlanImportError(ValueError):
    pass


def _normalise_header(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _clean_text(value):
    if pd.isna(value):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_amount(value, row_number):
    try:
        amount = Decimal(_clean_text(value).replace(',', ''))
    except (InvalidOperation, AttributeError):
        raise ProcurementPlanImportError(
            u'แถวที่ {}: จำนวนเงิน "{}" ไม่ถูกต้อง'.format(row_number, _clean_text(value))
        )
    if amount < 0:
        raise ProcurementPlanImportError(u'แถวที่ {}: จำนวนเงินต้องไม่ติดลบ'.format(row_number))
    return amount


def parse_procurement_plan_workbook(file_obj, fiscal_year):
    """Return ``(fiscal_year, rows)`` from the standard MT workbook."""
    try:
        excel_file = pd.ExcelFile(file_obj)
    except Exception as exc:
        raise ProcurementPlanImportError(u'ไม่สามารถอ่านไฟล์ Excel ได้: {}'.format(exc))

    if DATA_SHEET not in excel_file.sheet_names:
        raise ProcurementPlanImportError(u'ไม่พบชีต "{}"'.format(DATA_SHEET))
    frame = pd.read_excel(excel_file, sheet_name=DATA_SHEET, header=1, dtype=object)
    columns = {_normalise_header(column): column for column in frame.columns}

    missing = [label for label in REQUIRED_COLUMNS.values() if _normalise_header(label) not in columns]
    if missing:
        raise ProcurementPlanImportError(u'ไม่พบคอลัมน์ที่จำเป็น: {}'.format(', '.join(missing)))

    def column_value(record, label):
        original = columns.get(_normalise_header(label))
        return record.get(original) if original is not None else None

    rows = []
    errors = []
    for index, record in frame.iterrows():
        row_number = index + 3
        item = _clean_text(column_value(record, REQUIRED_COLUMNS['item']))
        if not item:
            continue
        try:
            if len(item) > 255:
                raise ProcurementPlanImportError(
                    u'แถวที่ {}: รายการยาวเกิน 255 ตัวอักษร'.format(row_number)
                )
            functional_area = _clean_text(column_value(record, REQUIRED_COLUMNS['product_code']))
            product_code = functional_area.split()[0] if functional_area else ''
            product_name = functional_area[len(product_code):].strip() if product_code else ''
            cost_center = _clean_text(column_value(record, REQUIRED_COLUMNS['cost_center']))
            funding_source = _clean_text(column_value(record, REQUIRED_COLUMNS['funding_source']))
            method = _clean_text(column_value(record, REQUIRED_COLUMNS['procurement_method']))
            for label, value in ((u'ผลผลิต/โครงการ/รายงาน', product_code),
                                 (u'ศูนย์ต้นทุน', cost_center),
                                 (u'แหล่งงบประมาณ', funding_source),
                                 (u'วิธีการจัดซื้อจัดจ้าง', method)):
                if not value:
                    raise ProcurementPlanImportError(u'แถวที่ {}: ไม่ได้ระบุ{}'.format(row_number, label))

            external_order_no = _clean_text(column_value(record, OPTIONAL_COLUMNS['external_order_no']))
            if len(external_order_no) > 64:
                raise ProcurementPlanImportError(u'แถวที่ {}: External order no. ยาวเกิน 64 ตัวอักษร'.format(row_number))

            rows.append({
                'row_number': row_number,
                'fiscal_year': fiscal_year,
                'item': item,
                'product_code': product_code,
                'product_name': product_name,
                'cost_center': cost_center,
                'procurement_method': method,
                'amount': _parse_amount(column_value(record, REQUIRED_COLUMNS['amount']), row_number),
                'funding_source': funding_source,
                'fund_code': external_order_no or None,
            })
        except ProcurementPlanImportError as exc:
            errors.append(str(exc))

    if errors:
        raise ProcurementPlanImportError('\n'.join(errors))
    if not rows:
        raise ProcurementPlanImportError(u'ไม่พบรายการสำหรับนำเข้าในชีต "{}"'.format(DATA_SHEET))
    return fiscal_year, rows


def normalise_procurement_method(value):
    text = _clean_text(value).lower()
    if 'e-bidding' in text or 'e-bidding' in text.replace(' ', ''):
        return u'ประกาศเชิญชวนทั่วไป(E-Bidding)'
    if u'คัดเลือก' in text:
        return u'วิธีคัดเลือก'
    if u'เฉพาะเจาะจง' in text:
        return u'วิธีเฉพาะเจาะจง'
    if u'รับบริจาค' in text or u'รับโอน' in text:
        return u'รับบริจาค/รับโอน'
    return u'อื่นๆ'
