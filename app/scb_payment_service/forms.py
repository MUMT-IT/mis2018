# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets
from wtforms_alchemy import model_form_factory

from app.main import db
from app.scb_payment_service.models import ScbPaymentRecord

BaseModelForm = model_form_factory(FlaskForm)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ScbPaymentRecordForm(ModelForm):
    class Meta:
        model = ScbPaymentRecord