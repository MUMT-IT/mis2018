# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets, FileField, IntegerField, RadioField, SelectField
from wtforms.validators import DataRequired
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
    # Calculate day to month
    days = IntegerField(u'ระยะเวลา')
    division = SelectField(u'ช่วงเวลา', choices=[(0, u'วัน'),
                                            (1, u'เดือน'),
                                            (2, u'ปี')])
    category = QuerySelectField(u'หมวดหมู่/ประเภท', query_factory=lambda: ProcurementCategory.query.all(),
                                blank_text='Select Category..', allow_blank=False)
    org = QuerySelectField(query_factory=lambda: Org.query.all(),
                                 get_label='name',
                                 label=u'ภาควิชา/หน่วยงาน')
    location = QuerySelectField(u'สถานที่', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)
    status = QuerySelectField(u'สถานะ', query_factory=lambda: ProcurementStatus.query.all(),
                              blank_text='Select status..', allow_blank=False)
    available = SelectField(u'สภาพของสินทรัพย์',
                         choices=[(c, c) for c in [u'ใช้งาน', u'เสื่อมสภาพ/รอจำหน่าย', u'หมดความจำเป็น']],
                         coerce=unicode,
                         validators=[DataRequired()])
    purchasing_type = SelectField(u'จัดซื้อด้วยเงิน',
                         choices=[(c, c) for c in [u'เงินงบประมาณแผ่นดิน', u'เงินรายได้ส่วนงาน']])


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


class ProcurementApprovalForm(ModelForm):
    class Meta:
        model = ProcurementCommitteeApproval

    checking_result = RadioField(u'ยืนยัน',
                         choices=[(c, c) for c in [u'ตรวจสอบครุภัณฑ์ถูกต้อง', u'ตรวจสอบครุภัณฑ์ไม่ถูกต้อง']],
                         coerce=unicode,
                         validators=[DataRequired()])