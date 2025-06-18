from flask_wtf import FlaskForm
from wtforms import FileField, FieldList, FormField, RadioField
from wtforms.validators import DataRequired, Length
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField
from app.academic_services.models import *
from flask_login import current_user
from sqlalchemy import or_

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    type = QuerySelectField('ประเภท', query_factory=lambda: ServiceCustomerType.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกประเภท', get_label='type')


class ServiceCustomerAddressForm(ModelForm):
    class Meta:
        model = ServiceCustomerAddress


def formatted_request_data():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceRequest.query.filter(ServiceRequest.is_paid, or_(ServiceRequest.admin.has(id=current_user.id),
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


class ServiceCustomerAddressForm(ModelForm):
    class Meta:
        model = ServiceCustomerAddress

    type = RadioField('ประเภทที่อยู่', choices=[(c, c) for c in ['ที่อยู่จัดส่งเอกสาร', 'ที่อยู่ใบเสนอราคา/ใบแจ้งหนี้/ใบกำกับภาษี']],
                      validators=[DataRequired()])


class ServiceQuotationItemForm(ModelForm):
    class Meta:
        model = ServiceQuotationItem
        exclude = ['item', 'quantity', 'unit_price', 'total_price']


class ServiceQuotationForm(ModelForm):
    class Meta:
        model = ServiceQuotation
        exclude = ['total_price']
    quotation_items = FieldList(FormField(ServiceQuotationItemForm, default=ServiceQuotationItem))


class ServiceInvoiceForm(ModelForm):
    class Meta:
        model = ServiceInvoice
        exclude = ['total_price']