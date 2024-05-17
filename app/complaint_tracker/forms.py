# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField
from app.complaint_tracker.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ComplaintActionRecordForm(ModelForm):
    class Meta:
        model = ComplaintActionRecord


class QuerySelectMultipleFieldAppendable(QuerySelectMultipleField):
    def __init__(self, label, validators=None, **kwargs):
        super(QuerySelectMultipleFieldAppendable, self).__init__(label, validators, **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            if self.allow_blank and valuelist[0] == '__None':
                self.data = None
            else:
                self._data = []
                for value in valuelist:
                    if not value.isdigit():
                        tag = ComplaintTag.query.filter_by(tag=value).first()
                        if not tag:
                            tag = ComplaintTag(tag=value)
                            db.session.add(tag)
                            db.session.commit()
                        self._data.append(tag)
                    else:
                        tag = ComplaintTag.query.get(int(value))
                        if tag:
                            self._data.append(tag)


class ComplaintRecordForm(ModelForm):
    class Meta:
        model = ComplaintRecord
    status = QuerySelectField('สถานะ', query_factory=lambda: ComplaintStatus.query.all(), allow_blank=True,
                              blank_text='กรุณาเลือกสภานะ')
    priority = QuerySelectField('ระดับความสำคัญ', query_factory=lambda: ComplaintPriority.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกระดับความสำคัญ')
    topic = QuerySelectField('หัวข้อ', query_factory=lambda: ComplaintTopic.query.all(), allow_blank=True)
    subtopic = QuerySelectField('พันธกิจ', query_factory=lambda: ComplaintSubTopic.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกพันธกิจ', get_label='subtopic')
    type = QuerySelectField('ประเภท', query_factory=lambda: ComplaintType.query.all(), allow_blank=True,
                            blank_text='กรุณาเลือกประเภท', get_label='type')
    tags = QuerySelectMultipleFieldAppendable('แท็กเรื่อง', query_factory=lambda: ComplaintTag.query.all(),
                                              get_label='tag')
    file_upload = FileField('File Upload')


class ComplaintInvestigatorForm(ModelForm):
    class Meta:
        model = ComplaintInvestigator
    invites = QuerySelectMultipleField(query_factory=lambda: ComplaintAdmin.query.all())

