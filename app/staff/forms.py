# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import widgets
from wtforms.validators import DataRequired
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from .models import StaffSeminar, StaffSeminarMission
from app.main import db

BaseModelForm = model_form_factory(FlaskForm)

class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session

class StaffSeminarForm(ModelForm):
    class Meta:
        model = StaffSeminar
    missions = QuerySelectMultipleField(u'พัฒนาในด้าน', get_label='mission', validators=[DataRequired()],
                                       query_factory=lambda: StaffSeminarMission.query.all(),
                                       widget=widgets.ListWidget(prefix_label=False),
                                       option_widget=widgets.CheckboxInput()
                                       )
