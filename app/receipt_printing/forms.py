# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FormField, FieldList, FileField, StringField, RadioField, Field, TextAreaField, SelectField, \
    PasswordField, SubmitField
from wtforms.validators import DataRequired
from wtforms.widgets import TextInput
from wtforms_alchemy import model_form_factory, QuerySelectField
from wtforms_components import EmailField

from app.main import db
from app.models import CostCenter, IOCode, Mission, Org
from app.receipt_printing.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class NumberTextField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return str(self.data)
        else:
            return ''

    def process_formdata(self, value):
        if value:
            self.data = float(value[0].replace(',',''))
        else:
            self.data = None


class ReceiptListForm(ModelForm):
    class Meta:
        model = ElectronicReceiptItem

    price = NumberTextField('จำนวน')
    cost_center = QuerySelectField('Cost Center',
                                   query_factory=lambda: CostCenter.query.all(),
                                   get_label='id', blank_text='Select Cost Center..', allow_blank=True
    ,validators=[DataRequired(message=('Cost Center is required'))])
    internal_order_code = QuerySelectField('Internal Order Code',
                                      query_factory=lambda: IOCode.query.filter_by(is_active=True),
                                      blank_text='Select Internal Order/IO..', allow_blank=True
                                    ,validators=[DataRequired(message=('Internal Order Code is required'))])
    gl = QuerySelectField('GL',
                          query_factory=lambda: ElectronicReceiptGL.query.all(),
                          blank_text='Select GL..', allow_blank=True,
                          validators=[DataRequired(message=('GL is required'))])


class ReceiptDetailForm(ModelForm):
    class Meta:
        model = ElectronicReceiptDetail
        only = ['number', 'copy_number', 'book_number', 'comment', 'paid', 'cancelled', 'cancel_comment',
                'payment_method', 'paid_amount', 'card_number', 'cheque_number', 'other_payment_method']

    payer = SelectField('Received Money From', validate_choice=False)
    bank_name = QuerySelectField('Bank Name',
                                 query_factory=lambda: ElectronicReceiptBankName.query.all(),
                                 blank_text='Select bank name..', allow_blank=True)
    address = TextAreaField('ที่อยู่ในใบเสร็จรับเงิน')

    items = FieldList(FormField(ReceiptListForm, default=ElectronicReceiptItem), min_entries=1)


class ReceiptRequireForm(ModelForm):
    class Meta:
        model = ElectronicReceiptRequest

    upload = FileField(u'อัพโหลดไฟล์')


class ReportDateForm(FlaskForm):
   created_datetime = StringField(u'วันที่ออกใบเสร็จ')


class CostCenterForm(ModelForm):
    class Meta:
        model = CostCenter
    cost_center = StringField(u'Cost Center')


class IOCodeForm(ModelForm):
    class Meta:
        model = IOCode

    is_active = RadioField(u'สถานะ',
                           choices=[(c, c) for c in [u'Active', u'Inactive']],
                           validators=[DataRequired()])
    mission = QuerySelectField('mission', query_factory=lambda: Mission.query.all(),
                               get_label='name', blank_text='Select Mission..', allow_blank=True)
    org = QuerySelectField(query_factory=lambda: Org.query.all(),
                           get_label='name',
                           label=u'ภาควิชา/หน่วยงาน',
                           blank_text='Select Org..', allow_blank=True)
    io = StringField(u'Internal Order/IO')


class GLForm(ModelForm):
    class Meta:
        model = ElectronicReceiptGL
    gl = StringField(u'GL')


class ReceiptInfoPayerForm(ModelForm):
    class Meta:
        model = ElectronicReceiptReceivedMoneyFrom


class PasswordOfSignDigitalForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    cancel_comment = TextAreaField('cancel_comment', validators=[DataRequired()])


class SendMailToCustomerForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired()])









