# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FormField, FieldList, FileField
from wtforms_alchemy import model_form_factory

from app.main import db
from app.receipt_printing.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ReceiptListForm(ModelForm):
    class Meta:
        model = ElectronicReceiptItem


class ReceiptDetailForm(ModelForm):
    class Meta:
        model = ElectronicReceiptDetail
        only = ['number', 'copy_number', 'book_number', 'comment', 'paid', 'cancelled', 'cancel_comment',
                'payment_method', 'paid_amount', 'card_number', 'cheque_number', 'other_payment_method', 'address',
                'received_from', 'gl', 'cost_center', 'internal_order', 'bank_name']

    items = FieldList(FormField(ReceiptListForm, default=ElectronicReceiptItem), min_entries=1)


class ReceiptRequireForm(ModelForm):
    class Meta:
        model = ElectronicReceiptRequest

    upload = FileField(u'อัพโหลดไฟล์')










