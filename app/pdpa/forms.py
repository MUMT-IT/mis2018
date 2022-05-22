# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory, QuerySelectMultipleField

from app.main import db
from app.models import CoreService, Data
from app.pdpa.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


def request_form_factory(service):
    class PDPARequestForm(ModelForm):
        class Meta:
            model = PDPARequest
        datasets = QuerySelectMultipleField(u'ชุดข้อมูล', get_label='name', validators=[DataRequired()],
                                            query_factory=lambda: [d for d in service.datasets if d.personal is True],
                                            widget=widgets.ListWidget(prefix_label=False),
                                            option_widget=widgets.CheckboxInput())
    return PDPARequestForm
