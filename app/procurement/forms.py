# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets, FileField
from wtforms_alchemy import (model_form_factory, QuerySelectField)
from .models import *
from ..models import Org

BaseModelForm = model_form_factory(FlaskForm)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session

class CreateProcurementForm(ModelForm):
    class Meta:
        model = ProcurementDetail
    upload = FileField(u'อัพโหลดหลักฐานการจ่าย')
    category = QuerySelectField(u'หมวดหมู่/ประเภท', query_factory=lambda: ProcurementCategory.query.all(),
                                blank_text='Select Category..', allow_blank=False)
    organiser = QuerySelectField(query_factory=lambda: Org.query.all(),
                                 get_label='name',
                                 label=u'ภาควิชา')
    location = QuerySelectField(u'สถานที่', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)

class ProcurementRecordForm(ModelForm):
    class Meta:
        model = ProcurementRecord
        exclude = ['updated_at']

    location = QuerySelectField(u'สถานที่', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)
    status = QuerySelectField(u'สถานะ', query_factory=lambda: ProcurementStatus.query.all(),
                                blank_text='Select status..', allow_blank=False)



