# -*- coding:utf-8 -*-
import datetime

from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets, FileField, RadioField, SelectField, FieldList, \
    FormField, Field, SubmitField, StringField
from wtforms.validators import DataRequired
from wtforms.widgets import TextInput
from wtforms_alchemy import (model_form_factory, QuerySelectField)
from .models import *
from ..models import Org
from ..staff.models import StaffPersonalInfo

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

    location = QuerySelectField(u'สถานที่',
                                query_factory=lambda: RoomResource.query.order_by(RoomResource.number.asc()),
                                blank_text='Select location..', allow_blank=True)
    status = QuerySelectField(u'สถานะ', query_factory=lambda: ProcurementStatus.query.all(),
                              blank_text='Select status..', allow_blank=False)
    staff_responsible = QuerySelectField(u'ผู้ดูแลครุภัณฑ์', query_factory=lambda: StaffAccount.get_active_accounts(),
                                         get_label='personal_info',
                                         blank_text='Select staff', allow_blank=True)


class DatePickerField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return self.data.strftime('%d/%m/%Y')
        else:
            return ''

    def process_formdata(self, value):
        if value[0]:
            self.data = datetime.datetime.strptime(value[0], '%d/%m/%Y')
        else:
            self.data = None


class ProcurementDetailForm(ModelForm):
    class Meta:
        model = ProcurementDetail
        exclude = ['image']

    image_file_upload = FileField(u'อัพโหลดรูปภาพ')
    category = QuerySelectField(u'หมวดหมู่/ประเภท', query_factory=lambda: ProcurementCategory.query.all(),
                                blank_text='Select Category..', allow_blank=True)
    org = QuerySelectField(query_factory=lambda: Org.query.all(),
                           get_label='name',
                           label=u'ภาควิชา/หน่วยงาน',
                           blank_text='Select Org..', allow_blank=True)
    available = SelectField(u'สภาพของสินทรัพย์',
                            choices=[(c, c) for c in [u'ใช้งาน', u'เสื่อมสภาพ/รอจำหน่าย', u'หมดความจำเป็น']],
                            validators=[DataRequired()])
    purchasing_type = QuerySelectField(u'จัดซื้อด้วยเงิน', query_factory=lambda: ProcurementPurchasingType.query.all(),
                                       get_label='purchasing_type',
                                       blank_text='Select type..',
                                       allow_blank=True)
    records = FieldList(FormField(ProcurementRecordForm, default=ProcurementRecord), min_entries=1)
    received_date = DatePickerField(u'วันที่ได้รับ')
    start_guarantee_date = DatePickerField(u'วันที่เริ่มประกัน')
    end_guarantee_date = DatePickerField(u'วันที่สิ้นสุดประกัน')


class ProcurementUpdateRecordForm(ModelForm):
    class Meta:
        model = ProcurementRecord

    location = QuerySelectField(u'สถานที่',
                                query_factory=lambda: RoomResource.query.order_by(RoomResource.number.asc()),
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
                                 validators=[DataRequired()])


class ProcurementAddImageForm(ModelForm):
    class Meta:
        model = ProcurementDetail
        only = ['image']

    image_upload = FileField(u'อัพโหลดรูปภาพ')


class ProcurementRoomForm(ModelForm):
    class Meta:
        model = RoomResource


class ProcurementComputerInfoForm(ModelForm):
    class Meta:
        model = ProcurementInfoComputer

    user = QuerySelectField(u'ผู้ใช้งานหลัก', query_factory=lambda: StaffAccount.get_active_accounts(),
                            get_label='personal_info', allow_blank=True)
    cpu = QuerySelectField('CPU', query_factory=lambda: ProcurementInfoCPU.query.all(), allow_blank=True)
    ram = QuerySelectField('RAM', query_factory=lambda: ProcurementInfoRAM.query.all(), allow_blank=True)
    windows_version = QuerySelectField(u'รุ่นของระบบปฏิบัติการ Windows',
                                       query_factory=lambda: ProcurementInfoWindowsVersion.query.all(),
                                       allow_blank=True)


class ProcurementSurveyComputerForm(ModelForm):
    class Meta:
        model = ProcurementSurveyComputer
        exclude = ['survey_date']


    satisfaction_with_speed_of_use = RadioField(u'ความเร็วในการทำงาน',
                                                choices=[(c, c) for c in [u'ไม่พอใจมาก', u'พอใจ', u'พอใจมาก']],
                                                validators=[DataRequired()])
    satisfaction_with_continuous_work = RadioField(u'การทำงานต่อเนื่อง ไม่ล่ม หรือค้าง',
                                                   choices=[(c, c) for c in [u'ไม่พอใจมาก', u'พอใจ', u'พอใจมาก']],
                                                   validators=[DataRequired()])
    satisfaction_with_enough_space = RadioField(u'พื้นที่พอเพียง',
                                                choices=[(c, c) for c in [u'ไม่พอใจมาก', u'พอใจ', u'พอใจมาก']],
                                                validators=[DataRequired()])
