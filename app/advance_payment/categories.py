"""Shared finance category labels and context-specific selectable codes."""

CATEGORY_LABELS = {
    1: "ค่าตอบแทน",
    2: "ค่าใช้สอย",
    3: "ค่าวัสดุ",
    4: "ค่าสาธารณูปโภค",
    5: "อื่น ๆ",
    6: "โอนคืนบัญชีหน่วย",
    7: "สวัสดิการ",
    8: "เงินอุดหนุน",
}

CATEGORY_EXAMPLES = {
    1: "ค่าตอบแทนผู้สอน/วิทยากร, เบี้ยประชุม, ค่าทำงานนอกเวลา",
    2: "ค่าเดินทาง, ค่าจัดกิจกรรม/โครงการ, ค่าเลี้ยงรับรอง",
    3: "วัสดุสำนักงาน, วัสดุงานครัว/จัดประชุม, วัสดุสิ้นเปลือง, ค่ารถตู้",
    4: "ค่าไฟฟ้า, ค่าน้ำประปา, ค่าโทรศัพท์, ค่าอินเทอร์เน็ต, ค่าไปรษณีย์",
    5: "ค่ารักษาพยาบาล",
}

CATEGORY_CHOICES = {
    code: f"{label} (เช่น {CATEGORY_EXAMPLES[code]})"
    if code in CATEGORY_EXAMPLES else label
    for code, label in CATEGORY_LABELS.items()
}

PETTY_CASH_EXPENSE_CODES = (1, 2, 3, 4, 5)
RETURN_EXPENSE_CODES = (1, 2, 3, 4, 7, 8)

PETTY_CASH_EXPENSE_CHOICES = tuple(
    (code, CATEGORY_CHOICES[code]) for code in PETTY_CASH_EXPENSE_CODES
)
RETURN_EXPENSE_CHOICES = tuple(
    (code, CATEGORY_LABELS[code]) for code in RETURN_EXPENSE_CODES
)


def parse_return_item_categories(form, receipt_items):
    """Require exactly one allowed finance category per noncash receipt item."""
    noncash_items = [item for item in receipt_items if not item.is_cash]
    expected = {f"category_{item.id}" for item in noncash_items}
    submitted = {key for key in form if key.startswith("category_")}
    if submitted != expected:
        raise ValueError("กรุณาเลือกหมวดหมู่ให้ครบทุกใบเสร็จ")

    selected = {}
    for item in noncash_items:
        values = form.getlist(f"category_{item.id}")
        if len(values) != 1 or not values[0].strip().isdigit():
            raise ValueError("กรุณาเลือกหมวดหมู่ให้ถูกต้อง")
        code = int(values[0].strip())
        if code not in RETURN_EXPENSE_CODES:
            raise ValueError("หมวดหมู่ของใบเสร็จไม่ถูกต้อง")
        selected[item.id] = code
    return selected
