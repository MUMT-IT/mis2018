# -*- coding:utf-8 -*-
from wtforms.validators import DataRequired

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, widgets, BooleanField
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from .models import *
from app.models import Mission


BaseModelForm = model_form_factory(FlaskForm)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class CoreServiceForm(BaseModelForm):
    class Meta:
        model = CoreService
        only = ['service']
    mission = QuerySelectField(u'พันธกิจ', query_factory=lambda: Mission.query.all(),
                                get_label='name', blank_text='Select mission..', allow_blank=False)
