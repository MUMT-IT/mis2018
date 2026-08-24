# -*- coding:utf-8 -*-
import datetime

from flask_wtf import FlaskForm
from wtforms import (SelectMultipleField,
                     widgets,
                     FileField,
                     RadioField,
                     SelectField,
                     FieldList,
                     FormField,
                     Field,
                     StringField,
                     TextAreaField,
                     BooleanField,
                     SubmitField,
                     IntegerField,
                     DecimalField
                     )
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import TextInput
from wtforms_alchemy import (model_form_factory, QuerySelectField)
from .models import *
from ..models import Org, CostCenter
from ..staff.models import StaffPersonalInfo, StaffAccount

BaseModelForm = model_form_factory(FlaskForm)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ProcurementFundingSourceForm(FlaskForm):
    code = StringField(u'รหัสแหล่งงบประมาณ', validators=[DataRequired(), Length(max=64)])
    name = StringField(u'ชื่อแหล่งงบประมาณ', validators=[DataRequired(), Length(max=255)])
    description = TextAreaField(u'รายละเอียด', validators=[Optional()])
    is_active = BooleanField(u'ใช้งาน', default=True)
    submit = SubmitField(u'บันทึก')


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


class ProcurementPlanForm(FlaskForm):
    fiscal_year = IntegerField(u'ปีงบประมาณ', validators=[DataRequired()])
    funding_source = QuerySelectField(
        u'แหล่งงบประมาณ',
        query_factory=lambda: ProcurementFundingSource.query.filter_by(is_active=True).order_by(
            ProcurementFundingSource.code.asc()
        ).all(),
        get_label=lambda source: str(source),
        allow_blank=False,
    )
    item = StringField(u'รายการพัสดุ/รายการจัดซื้อจัดจ้าง', validators=[DataRequired(), Length(max=255)])
    output_project_report = TextAreaField(u'ผลผลิต/โครงการ/รายงาน', validators=[DataRequired()])
    cost_center = QuerySelectField(
        u'ศูนย์ต้นทุน',
        query_factory=lambda: CostCenter.query.order_by(CostCenter.id.asc()).all(),
        get_label='id',
        allow_blank=False,
    )
    procurement_method = SelectField(
        u'วิธีการจัดซื้อจัดจ้าง',
        choices=[
            (u'ประกาศเชิญชวนทั่วไป(E-Bidding)', u'ประกาศเชิญชวนทั่วไป(E-Bidding)'),
            (u'วิธีคัดเลือก', u'วิธีคัดเลือก'),
            (u'วิธีเฉพาะเจาะจง', u'วิธีเฉพาะเจาะจง'),
            (u'รับบริจาค/รับโอน', u'รับบริจาค/รับโอน'),
            (u'อื่นๆ', u'อื่นๆ'),
        ],
        validators=[DataRequired()],
    )
    amount = DecimalField(u'จำนวนเงิน', places=2, validators=[DataRequired()])
    fund_code = StringField(u'รหัสทุน', validators=[Optional(), Length(max=64)])
    responsible_staff = QuerySelectField(
        u'ผู้รับผิดชอบ',
        query_factory=lambda: StaffAccount.get_active_accounts(),
        get_label='fullname',
        allow_blank=False,
    )
    vendor = QuerySelectField(
        u'บริษัทคู่สัญญา',
        query_factory=lambda: ProcurementVendor.query.filter_by(is_active=True).order_by(
            ProcurementVendor.name.asc()
        ).all(),
        get_label='name',
        allow_blank=True,
        blank_text='ยังไม่ระบุ',
    )
    principle_approval_date = DatePickerField(u'วันที่อนุมัติหลักการ')
    tor_completed_date = DatePickerField(u'วันที่จัดทำ TOR แล้วเสร็จ')
    quotation_submission_date = DatePickerField(u'วันที่ยื่นเสนอราคา')
    contract_signed_date = DatePickerField(u'วันที่ลงนามสัญญา')
    inspection_date = DatePickerField(u'วันที่ตรวจรับ')
    note = TextAreaField(u'หมายเหตุ', validators=[Optional()])
    submit = SubmitField(u'บันทึก')


class ProcurementPlanCommitteeMemberForm(FlaskForm):
    staff = QuerySelectField(
        u'บุคลากร',
        query_factory=lambda: StaffAccount.get_active_accounts(),
        get_label='fullname',
        allow_blank=False,
    )
    role = SelectField(
        u'บทบาท',
        choices=[
            ('chairman', u'ประธาน'),
            ('committee', u'กรรมการ'),
            ('secretary', u'เลขานุการ'),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField(u'เพิ่มกรรมการ')


class ProcurementDetailForm(ModelForm):
    class Meta:
        model = ProcurementDetail
        exclude = ['image_url', 'is_qrcode_attached']

    image_file_upload = FileField(u'อัพโหลดรูปภาพ')
    cost_center = SelectField(u'ศูนย์ต้นทุน',
                              choices=[('Select Cost Center.. ', u'Select Cost Center..'),
                                       ('C0401000', u'C0401000'), ('C0401301', u'C0401301'),
                                       ('C0401001', u'C0401001'), ('C0401002', u'C0401002'),
                                       ('C0401003', u'C0401003'), ('C0401004', u'C0401004'),
                                       ('C0401005', u'C0401005'), ('C0402001', u'C0402001'),
                                       ('C0401100', u'C0401100'), ('C0401200', u'C0401200'),
                                       ('C0401400', u'C0401400'), ('C0401500', u'C0401500'),
                                       ('C0402000', u'C0402000'), ('C0402002', u'C0402002'),
                                       ('C0402003', u'C0402003'), ('C0402004', u'C0402004'),
                                       ('C0402005', u'C0402005'), ('C0403000', u'C0403000'),
                                       ('C0403001', u'C0403001'), ('C0403002', u'C0403002'),
                                       ('C0403003', u'C0403003'), ('C0403004', u'C0403004'),
                                       ('C0403005', u'C0403005'), ('C0404000', u'C0404000'),
                                       ('C0404001', u'C0404001'), ('C0404002', u'C0404002'),
                                       ('C0404003', u'C0404003'), ('C0404004', u'C0404004'),
                                       ('C0404005', u'C0404005'), ('C0405000', u'C0405000'),
                                       ('C0405001', u'C0405001'), ('C0405002', u'C0405002'),
                                       ('C0405003', u'C0405003'), ('C0405004', u'C0405004'),
                                       ('C0405005', u'C0405005'), ('C0406000', u'C0406000'),
                                       ('C0406001', u'C0406001'), ('C0406002', u'C0406002'),
                                       ('C0406003', u'C0406003'), ('C0406004', u'C0406004'),
                                       ('C0406005', u'C0406005'), ('C0407000', u'C0407000'),
                                       ('C0407001', u'C0407001'), ('C0407002', u'C0407002'),
                                       ('C0407003', u'C0407003'), ('C0407004', u'C0407004'),
                                       ('C0407005', u'C0407005'), ('C0408000', u'C0408000'),
                                       ('C0408001', u'C0408001'), ('C0408002', u'C0408002'),
                                       ('C0408003', u'C0408003'), ('C0408004', u'C0408004'),
                                       ('C0408005', u'C0408005'), ('C0409000', u'C0409000'),
                                       ('C0409001', u'C0409001'), ('C0409002', u'C0409002'),
                                       ('C0409003', u'C0409003'), ('C0409004', u'C0409004'),
                                       ('C0409005', u'C0409005'), ('C0410000', u'C0410000'),
                                       ('C0410001', u'C0410001'), ('C0410002', u'C0410002'),
                                       ('C0410003', u'C0410003'), ('C0410004', u'C0410004'),
                                       ('C0410005', u'C0410005'), ('C0411000', u'C0411000'),
                                       ('C0411001', u'C0411001'), ('C0411002', u'C0411002'),
                                       ('C0411003', u'C0411003'), ('C0411004', u'C0411004'),
                                       ('C0411005', u'C0411005')
                                       ])
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
                                blank_text='-เลือกสถานที่ตั้ง-', allow_blank=True)
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

    format_service = RadioField(u'รูปแบบการให้บริการ',
                                 choices=[(c, c) for c in [u'นำเครื่องมาด้วย', u'ไม่ได้นำเครื่องมาด้วย', u'การให้บริการอื่นๆ']],
                                 validators=[DataRequired()])
    staff = QuerySelectField(u'ผู้ใช้งานหลัก', query_factory=lambda: StaffAccount.get_active_accounts(),
                            get_label='personal_info', allow_blank=True)


class ProcurementApprovalForm(ModelForm):
    class Meta:
        model = ProcurementCommitteeApproval

    checking_result = RadioField(u'ยืนยัน',
                                 choices=[(c, c) for c in [u'ตรวจสอบครุภัณฑ์ถูกต้อง', u'ตรวจสอบครุภัณฑ์ไม่ถูกต้อง']],
                                 validators=[DataRequired()])


class ProcurementAddImageForm(ModelForm):
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


class ProcurementBorrowItemForm(ModelForm):
    class Meta:
        model = ProcurementBorrowItem


class ProcurementBorrowDetailForm(ModelForm):
    class Meta:
        model = ProcurementBorrowDetail
        exclude = ['created_date']

    type_of_purpose = RadioField(u'ความประสงค์ของยืมพัสดุ',
                                 choices=[(c, c) for c in [u'ยืมระหว่างส่วนงาน', u'บุคลากรยืม-ใช้ภายในพื้นที่ของมหาวิทยาลัย',
                                                           u'บุคลากรยืม-ใช้นอกพื้นที่ของมหาวิทยาลัย', u'บุคลากรหรือหน่วยงานภายนอกยืมใช้']],
                                 validators=[DataRequired()])
    items = FieldList(FormField(ProcurementBorrowItemForm, default=ProcurementBorrowItem), min_entries=1)


class ProcurementLocationForm(ModelForm):
    class Meta:
        model = ProcurementRecord
    location = QuerySelectField('สถานที่', query_factory=lambda: RoomResource.query.order_by(RoomResource.number.asc()),
                                blank_text='-เลือกสถานที่ตั้ง-', allow_blank=True)
