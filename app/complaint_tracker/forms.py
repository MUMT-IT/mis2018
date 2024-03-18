# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField
from app.complaint_tracker.models import *
from wtforms.validators import DataRequired

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ComplaintActionRecordForm(ModelForm):
    class Meta:
        model = ComplaintActionRecord


class ComplaintRecordForm(ModelForm):
    class Meta:
        model = ComplaintRecord
    status = QuerySelectField('สถานะ', query_factory=lambda: ComplaintStatus.query.all(), allow_blank=True)
    priority = QuerySelectField('ระดับความสำคัญ', query_factory=lambda: ComplaintPriority.query.all(), allow_blank=True)
    topic = QuerySelectField('หัวข้อ', query_factory=lambda: ComplaintTopic.query.all(), allow_blank=True)
    subtopic = QuerySelectField('หัวข้อย่อย', query_factory=lambda: ComplaintSubTopic.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกหัวข้อย่อย', get_label='subtopic')
    file_upload = FileField('File Upload')


class ComplaintInvestigatorForm(ModelForm):
    class Meta:
        model = ComplaintInvestigator
    invites = QuerySelectMultipleField(query_factory=lambda: ComplaintAdmin.query.all())

