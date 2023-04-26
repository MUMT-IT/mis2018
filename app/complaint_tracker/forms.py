# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FormField, FieldList
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.complaint_tracker.models import *


BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ComplaitActionRecordForm(ModelForm):
    class Meta:
        model = ComplaintActionRecord


class ComplaintRecordForm(ModelForm):
    class Meta:
        model = ComplaintRecord
    status = QuerySelectField(u'สถานะ', query_factory=lambda: ComplaintStatus.query.all())
    priority = QuerySelectField(u'ระดับความสำคัญ', query_factory=lambda: ComplaintPriority.query.all())
    actions = FieldList(FormField(ComplaitActionRecordForm, default=ComplaintActionRecord), min_entries=1)
