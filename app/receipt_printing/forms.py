# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FormField, FieldList, FileField, StringField
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.main import db
from app.models import CostCenter, IOCode
from app.receipt_printing.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ReceiptListForm(ModelForm):
    class Meta:
        model = ElectronicReceiptItem

    cost_center = QuerySelectField('Cost Center',
                                   query_factory=lambda: CostCenter.query.all(),
                                   get_label='id', blank_text='Select Cost Center..', allow_blank=True)
    internal_order_code = QuerySelectField('Internal Order Code',
                                      query_factory=lambda: IOCode.query.all(),
                                      blank_text='Select Internal Order/IO..', allow_blank=True)
    gl = QuerySelectField('GL',
                          query_factory=lambda: ElectronicReceiptGL.query.all(),
                          blank_text='Select GL..', allow_blank=True)


class ReceiptDetailForm(ModelForm):
    class Meta:
        model = ElectronicReceiptDetail
        only = ['number', 'copy_number', 'book_number', 'comment', 'paid', 'cancelled', 'cancel_comment',
                'payment_method', 'paid_amount', 'card_number', 'cheque_number', 'other_payment_method', 'address',
                'received_from', 'bank_name']

    items = FieldList(FormField(ReceiptListForm, default=ElectronicReceiptItem), min_entries=1)


class ReceiptRequireForm(ModelForm):
    class Meta:
        model = ElectronicReceiptRequest

    upload = FileField(u'อัพโหลดไฟล์')


class ReportDateForm(FlaskForm):
   created_datetime = StringField(u'วันที่ใบเสร็จ')











