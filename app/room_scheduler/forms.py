# -*- coding:utf-8 -*-

from wtforms.validators import DataRequired

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, widgets, BooleanField
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)

from app.main import db
from app.room_scheduler.models import RoomComplaint, RoomComplaintTopic

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class RoomComplaintForm(ModelForm):
    class Meta:
        model = RoomComplaint
        exclude = ['created_at', ]
    topics = QuerySelectMultipleField(u'Topics', get_label='topic', validators=[DataRequired()],
                                      allow_blank=True,
                                      blank_text=u'กรุณาระบุ',
                                      query_factory=lambda: RoomComplaintTopic.query.all(),
                                      widget=widgets.ListWidget(prefix_label=False),
                                      option_widget=widgets.CheckboxInput())
