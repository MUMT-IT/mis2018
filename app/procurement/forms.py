# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets, TextAreaField, TextField, SubmitField
from wtforms_alchemy import (model_form_factory, QuerySelectField)
from .models import *


BaseModelForm = model_form_factory(FlaskForm)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ProcurementRecordForm(ModelForm):
    class Meta:
        model = ProcurementRecord
        exclude = ['updated_at']

    location = QuerySelectField(u'สถานที่', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)
    status = QuerySelectField(u'สถานะ', query_factory=lambda: ProcurementStatus.query.all(),
                                blank_text='Select status..', allow_blank=False)
    category = QuerySelectField(u'หมวดหมู่/ประเภท', query_factory=lambda: ProcurementCategory.query.all(),
                                blank_text='Select Category..', allow_blank=False)
    list = TextField(u'ชื่อรายการครุภัณฑ์')
    code = TextField(u'รหัสครุภัณฑ์')
    model = TextField(u'รุ่น')
    size = TextField(u'ขนาด')
    maker = TextField(u'ผู้รับผิดชอบ')
    desc = TextAreaField(u'รายละเอียด')
    comment = TextField()
    submit = SubmitField()

