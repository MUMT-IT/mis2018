# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets, FileField, IntegerField
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
    image = FileField(u'อัพโหลดรูปภาพ')
    days = IntegerField(u'ระยะเวลา')
    category = QuerySelectField(u'หมวดหมู่/ประเภท', query_factory=lambda: ProcurementCategory.query.all(),
                                blank_text='Select Category..', allow_blank=False)
    org = QuerySelectField(query_factory=lambda: Org.query.all(),
                                 get_label='name',
                                 label=u'ภาควิชา/หน่วยงาน')
    location = QuerySelectField(u'สถานที่', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)
    status = QuerySelectField(u'สถานะ', query_factory=lambda: ProcurementStatus.query.all(),
                              blank_text='Select status..', allow_blank=False)


class ProcurementRecordForm(ModelForm):
    class Meta:
        model = ProcurementRecord
        exclude = ['updated_at']

    location = QuerySelectField(u'สถานที่', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)
    status = QuerySelectField(u'สถานะ', query_factory=lambda: ProcurementStatus.query.all(),
                                blank_text='Select status..', allow_blank=False)


class ProcurementCategoryForm(ModelForm):
    class Meta:
        model = ProcurementCategory


class ProcurementStatusForm(ModelForm):
    class Meta:
        model = ProcurementStatus


class ProcurementRequireForm(ModelForm):
    class Meta:
        model = ProcurementRequire

    procurement_no = QuerySelectField(query_factory=lambda: ProcurementDetail.query.all(),
                                 get_label='procurement_no',
                                 label=u'เลขครุภัณฑ์')
    location = QuerySelectField(u'สถานที่ให้บริการ', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)


class ProcurementMaintenanceForm(ModelForm):
    class Meta:
        model = ProcurementMaintenance

    service = QuerySelectField(query_factory=lambda: ProcurementRequire.query.all(),
                                 get_label='service',
                                 label=u'ชื่อเครื่อง/การบริการ')
    procurement_no = QuerySelectField(query_factory=lambda: ProcurementDetail.query.all(),
                                      get_label='procurement_no',
                                      label=u'เลขครุภัณฑ์')
    location = QuerySelectField(u'สถานที่ให้บริการ', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)