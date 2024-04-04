# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import RadioField
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


def create_record_form(record_id):
    class ComplaintRecordForm(ModelForm):
        class Meta:
            model = ComplaintRecord
        status = QuerySelectField('สถานะ', query_factory=lambda: ComplaintStatus.query.all(), allow_blank=True)
        priority = QuerySelectField('ระดับความสำคัญ', query_factory=lambda: ComplaintPriority.query.all(), allow_blank=True)
        topic = QuerySelectField('หัวข้อ', query_factory=lambda: ComplaintTopic.query.all(), allow_blank=True)
        subtopic = QuerySelectField('พันธกิจ', query_factory=lambda: ComplaintSubTopic.query.all(), allow_blank=True,
                                    blank_text='กรุณาเลือกพันธกิจ', get_label='subtopic')
        file_upload = FileField('File Upload')
        if record_id is None:
            agreement = RadioField(u'ความยินยอมในการเก็บรวบรวม ใช้ และเปิดเผยข้อมูล',
                                   choices=[(c, c) for c in ['ยินยอม', 'ไม่ยินยอม']],
                                   validators=[DataRequired()])
    return ComplaintRecordForm

class ComplaintInvestigatorForm(ModelForm):
    class Meta:
        model = ComplaintInvestigator
    invites = QuerySelectMultipleField(query_factory=lambda: ComplaintAdmin.query.all())

