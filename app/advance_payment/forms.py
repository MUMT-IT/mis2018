from flask import current_app
from wtforms import DateField, DecimalField, Form, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError
from datetime import date
from .models import db, StaffAccount


class RegistrationForm(Form):
    email = StringField("อีเมล", validators=[DataRequired(message="กรุณากรอกอีเมล")])
    password = PasswordField(
        "รหัสผ่าน",
        validators=[DataRequired(message="กรุณากรอกรหัสผ่าน")],
    )

    def validate_email(self, field):
        normalized_email = field.data.strip().lower()
        user = db.session.query(StaffAccount).filter_by(email=normalized_email).first()
        if user is not None:
            raise ValidationError("อีเมลนี้ถูกใช้งานในระบบแล้ว")


class LoginForm(Form):
    email = StringField("อีเมล", validators=[DataRequired(message="กรุณากรอกอีเมล")])
    password = PasswordField(
        "รหัสผ่าน",
        validators=[DataRequired(message="กรุณากรอกรหัสผ่าน")],
    )


class BorrowingTicketForm(Form):
    borrower_email = SelectField("เลือกผู้ยืม", validators=[Optional()])
    borrowing_ticket_purpose = StringField("ชื่อโครงการ/วัตถุประสงค์", validators=[DataRequired(message="กรุณากรอกชื่อโครงการ/วัตถุประสงค์")])
    aip_ref_no = StringField("อนุมัติในหลักการ (เลขที่หนังสือ)", validators=[Optional()])
    aip_ref_date = DateField("วันที่หนังสือได้รับการอนุมัติ", validators=[Optional()])
    required_budget = DecimalField("ยอดเงินยืม", validators=[DataRequired(message="กรุณาระบุยอดเงินยืมที่ถูกต้อง")])
    account_number = StringField("เลขที่บัญชี", validators=[DataRequired(message="กรุณากรอกเลขที่บัญชี")])
    borrowing_ticket_start_date = DateField("วันที่เริ่มต้นโครงการ", validators=[DataRequired(message="กรุณาระบุวันที่เริ่มต้นโครงการ")])
    borrowing_ticket_end_date = DateField("วันที่สิ้นสุดโครงการ", validators=[DataRequired(message="กรุณาระบุวันที่สิ้นสุดโครงการ")])
    submit = SubmitField("ส่งสัญญาเงินยืม")

    def validate_borrowing_ticket_end_date(self, field):
        if self.borrowing_ticket_start_date.data and field.data and field.data < self.borrowing_ticket_start_date.data:
            raise ValidationError("วันที่สิ้นสุดโครงการต้องเป็นวันเดียวกันหรือหลังจากวันที่เริ่มต้นโครงการ")
        if field.data and field.data < date.today():
            raise ValidationError("วันที่สิ้นสุดโครงการต้องไม่เป็นวันในอดีต")

class FundRequestForm(Form):
    form_type = StringField("ประเภทแบบฟอร์ม")
    
    requester_name = StringField("ชื่อ-นามสกุล ผู้เบิกเงิน", validators=[Optional()])
    requester_position = StringField("ตำแหน่ง ผู้เบิกเงิน", validators=[Optional()])
    
    department = StringField("หน่วยงาน")
    account_number = StringField("เลขบัญชีหน่วยงาน")
    
    ticket_number = StringField("เลขที่ใบเบิกเงิน") 
    request_date = DateField("วันที่เบิกเงิน", format="%Y-%m-%d", validators=[Optional()])
    
    amount = DecimalField("จำนวนเงิน", validators=[DataRequired(), NumberRange(min=0.01)], places=2)
    
    purpose = StringField("วัตถุประสงค์ในการเบิก", validators=[Optional()])
    items = StringField("รายการที่เบิก", validators=[Optional()])
    
    period_year = StringField("งวดวันที่ (เดือน/ปี)", validators=[Optional()])


class BankAccountInfoForm(Form):
    record_type = SelectField("ประเภทข้อมูล", validators=[DataRequired(message="กรุณาเลือกประเภทข้อมูล")])
    thai_name = StringField("ชื่อภาษาไทย", validators=[DataRequired(message="กรุณากรอกชื่อภาษาไทย")])
    created_at = StringField("วันที่", validators=[DataRequired(message="กรุณากรอกวันที่")])
    account_number = StringField("เลขที่บัญชี", validators=[DataRequired(message="กรุณากรอกเลขที่บัญชี")])
    submit = SubmitField("บันทึกข้อมูล")

class PettyCashClaimItemForm(Form):
    receipt_date = DateField("วันที่ตามใบเสร็จ", validators=[DataRequired(message="กรุณาระบุวันที่")])
    description = StringField("รายการ", validators=[DataRequired(message="กรุณากรอกรายการ")])
    amount = DecimalField("จำนวนเงิน", validators=[NumberRange(min=0.01, message="จำนวนเงินต้องมากกว่า 0")])
    category_type = StringField("ประเภทหมวดหมู่", validators=[DataRequired()])
    custom_category = StringField("หมวดหมู่อื่นๆ (ถ้ามี)")

class SubmitPettyCashClaimForm(Form):
    # ฟอร์มหลักสำหรับรองรับโครงสร้างตาราง petty_cash_claim_details
    pass
