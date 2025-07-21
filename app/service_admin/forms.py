from flask_wtf import FlaskForm
from wtforms import FileField, FieldList, FormField, RadioField, FloatField, PasswordField
from wtforms.validators import DataRequired, Length, Optional
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.academic_services.forms import ServiceCustomerContactForm
from app.academic_services.models import *
from flask_login import current_user
from sqlalchemy import or_

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class PasswordOfSignDigitalForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    type = QuerySelectField('ประเภท', query_factory=lambda: ServiceCustomerType.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกประเภท', get_label='type')
    customer_contacts = FieldList(FormField(ServiceCustomerContactForm, default=ServiceCustomerContact), min_entries=1)


def formatted_request_data():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id),
                                            ServiceRequest.lab.in_(sub_labs)))
    return query


def create_result_form(has_file):
    class ServiceResultForm(ModelForm):
        class Meta:
            model = ServiceResult
        if has_file:
            file_upload = FileField('File Upload')
            request = QuerySelectField('เลขใบคำร้องขอ', query_factory=lambda: formatted_request_data(), allow_blank=True,
                                       blank_text='กรุณาเลือกเลขใบคำร้องขอ')
    return  ServiceResultForm


def crate_address_form(use_type=False):
    class ServiceCustomerAddressForm(ModelForm):
        class Meta:
            model = ServiceCustomerAddress
        if use_type==True:
            address_type = RadioField('ประเภทที่อยู่', choices=[(c, c) for c in ['ที่อยู่จัดส่งเอกสาร', 'ที่อยู่ใบเสนอราคา/ใบแจ้งหนี้/ใบกำกับภาษี']],
                              validators=[DataRequired()])
        province = QuerySelectField('จังหวัด', query_factory=lambda: Province.query.all(), allow_blank=True,
                                    blank_text='กรุณาเลือกจังหวัด', get_label='name')
        district = QuerySelectField('เขต/อำเภอ', query_factory=lambda: District.query.all(), allow_blank=True,
                                    blank_text='กรุณาเลือกเขต/อำเภอ', get_label='name')
        subdistrict = QuerySelectField('แขวง/ตำบล', query_factory=lambda: Subdistrict.query.all(), allow_blank=True,
                                       blank_text='กรุณาเลือกแขวง/ตำบล', get_label='name')
    return ServiceCustomerAddressForm


def create_quotation_item_form(is_form=False):
    class ServiceQuotationItemForm(ModelForm):
        class Meta:
            model = ServiceQuotationItem
            if is_form == True:
                exclude = ['total_price']
            if is_form == False:
                exclude = ['item', 'quantity', 'unit_price', 'total_price']
    return ServiceQuotationItemForm


class ServiceQuotationForm(ModelForm):
    class Meta:
        model = ServiceQuotation
        exclude = ['digital_signature']
    quotation_items = FieldList(FormField(create_quotation_item_form(is_form=False), default=ServiceQuotationItem))


class ServiceSampleForm(ModelForm):
    class Meta:
        model = ServiceSample

    sample_integrity = RadioField('สภาพความสมบูรณ์ของตัวอย่าง', choices=[(c, c) for c in ['สมบูรณ์', 'ไม่สมบูรณ์']],
                                  default='สมบูรณ์', validators=[Optional()])
    packaging_sealed = RadioField('สภาพการปิดสนิทของภาชนะบรรจุตัวอย่าง', choices=[(c, c) for c in ['ปิดสนิท', 'ปิดไม่สนิท']],
                                  default='ปิดสนิท', validators=[Optional()])
    container_strength = RadioField('ความแข็งแรงของภาชนะบรรจุตัวอย่าง', choices=[(c, c) for c in ['แข็งแรง', 'ไม่แข็งแรง']],
                                    default='แข็งแรง', validators=[Optional()])
    container_durability = RadioField('ความคงทนของภาชนะบรรจุตัวอย่าง', choices=[(c, c) for c in ['คงทน', 'ไม่คงทน']],
                                    default='คงทน', validators=[Optional()])
    container_damage = RadioField('สภาพการแตก/หักของภาชนะบรรจุตัวอย่าง', choices=[(c, c) for c in ['ไม่แตก/หัก', 'แตก/หัก']],
                                    default='ไม่แตก/หัก', validators=[Optional()])
    info_match = RadioField('รายละเอียดบนภาชนะบรรจุตัวอย่างตรงกับใบคำขอรับบริการ', choices=[(c, c) for c in ['ตรง', 'ไม่ตรง']],
                                    default='ตรง', validators=[Optional()])
    same_production_lot = RadioField('ตัวอย่างชุดเดียวกันแต่มีหลายชิ้น (ถ้ามี)', choices=[(c, c) for c in ['ทุกชิ้นเป็นรุ่นผลิตเดียวกัน', 'มีชิ้นที่ไม่ใช่รุ่นผลิตเดียวกัน']],
                                    default='ทุกชิ้นเป็นรุ่นผลิตเดียวกัน', validators=[Optional()])


class ServiceInvoiceForm(ModelForm):
    class Meta:
        model = ServiceInvoice