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
    status = QuerySelectField('สถานะ', query_factory=lambda: ComplaintStatus.query.all(), allow_blank=True)
    priority = QuerySelectField('ระดับความสำคัญ', query_factory=lambda: ComplaintPriority.query.all(), allow_blank=True)
    actions = FieldList(FormField(ComplaitActionRecordForm, default=ComplaintActionRecord), min_entries=1)
    topic = QuerySelectField('หัวข้อ', query_factory=lambda: ComplaintTopic.query.all(), allow_blank=True)
