# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FormField, FieldList
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
        model = ElectronicReceiptList


class ReceiptDetailForm(ModelForm):
    class Meta:
        model = ElectronicReceiptDetail
        exclude = ['created_datetime']

    items = FieldList(FormField(ReceiptListForm, default=ElectronicReceiptList), min_entries=5)










