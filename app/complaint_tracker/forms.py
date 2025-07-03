# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import RadioField, FieldList, FormField, HiddenField, DateField
from wtforms.validators import Optional
from wtforms.widgets import TextInput
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


def create_record_form(record_id, topic_id):
    class ComplaintRecordForm(ModelForm):
        class Meta:
            model = ComplaintRecord
            if record_id:
                exclude = ['desc']
        status = QuerySelectField('สถานะ', query_factory=lambda: ComplaintStatus.query.all(), allow_blank=True,
                                  blank_text='กรุณาเลือกสถานะ')
        priority = QuerySelectField('ระดับความสำคัญ', query_factory=lambda: ComplaintPriority.query.all(), allow_blank=True,
                                    blank_text='กรุณาเลือกระดับความสำคัญ')
        topic = QuerySelectField('หัวข้อ', query_factory=lambda: ComplaintTopic.query.filter(ComplaintTopic.code!='misc'), allow_blank=True)
        if topic_id:
            subtopic = QuerySelectField('ด้านที่เกี่ยวข้อง', query_factory=lambda: ComplaintSubTopic.query.filter_by(topic_id=topic_id),
                                        allow_blank=True, blank_text='กรุณาเลือกด้านที่เกี่ยวข้อง', get_label='subtopic')
        type = QuerySelectField('ประเภท', query_factory=lambda: ComplaintType.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกประเภท', get_label='type')
        tags = QuerySelectMultipleFieldAppendable('แท็กเรื่อง', query_factory=lambda: ComplaintTag.query.all(),
                                                  get_label='tag')
        procurement_location = QuerySelectField('สถานที่ตั้งครุภัณฑ์ปัจจุบัน', query_factory=lambda: RoomResource.query.order_by(RoomResource.number.asc()),
                                                    allow_blank=True, blank_text='กรุณาเลือกสถานที่ตั้งครุภัณฑ์ปัจจุบัน')
        room = QuerySelectField('ห้อง', query_factory=lambda: RoomResource.query.order_by(RoomResource.number.asc()),
                                                    allow_blank=True, blank_text='กรุณาเลือกห้อง')
        file_upload = FileField('File Upload')
    return ComplaintRecordForm


class ComplaintInvestigatorForm(ModelForm):
    class Meta:
        model = ComplaintInvestigator

    invites = QuerySelectMultipleField(query_factory=lambda: StaffAccount.get_active_accounts(), get_label='fullname')


class ComplaintPerformanceReportForm(ModelForm):
    class Meta:
        model = ComplaintPerformanceReport


class ComplaintCoordinatorForm(ModelForm):
    class Meta:
        model = ComplaintCoordinator

    coordinators = QuerySelectMultipleField(query_factory=lambda: StaffAccount.get_active_accounts(), get_label='fullname')


class ComplaintCommitteeForm(ModelForm):
    class Meta:
        model = ComplaintCommittee

    staff = QuerySelectField(query_factory=lambda: StaffAccount.get_active_accounts(), get_label='fullname',
                                allow_blank=True, blank_text='กรุณาเลือกรายชื่อคณะกรรมการ')


class ComplaintRepairApprovalForm(ModelForm):
    class Meta:
        model = ComplaintRepairApproval

    mhesi_no_date = DateField('วันที่เลขที่ สอวช.', widget=TextInput())
    receipt_date = DateField('วันที่รับเอกสาร', widget=TextInput(), validators=[Optional()],)
    repair_type = RadioField('ประเภทใบอนุมัติหลักการซ่อม', choices=[('เร่งด่วน', 'เร่งด่วน'),
                                                                  ('ไม่เร่งด่วน (จ้าง/ซ่อม)', 'ไม่เร่งด่วน (จ้าง/ซ่อม)'),
                                                                  ('ไม่เร่งด่วน (จ้างซ่อม)', 'ไม่เร่งด่วน (จ้างซ่อม)')
                                                                  ])
    principle_approval_type = RadioField('ประเภทการขออนุมัติ', choices=[('ซื้อ', 'ซื้อ'), ('จ้าง', 'จ้าง')], validate_choice=False)
    cost_center = QuerySelectField(query_factory=lambda: CostCenter.query.all(), get_label='id',
                                   allow_blank=True, blank_text='กรุณาเลือกรหัสศูนย์ต้นทุน')
    io_code = QuerySelectField(query_factory=lambda: IOCode.query.all(), get_label='id', allow_blank=True,
                               blank_text='กรุณาเลือกรหัสใบสั่งงานภายใน')
    product_code = QuerySelectField(query_factory=lambda: ProductCode.query.all(), get_label='id', allow_blank=True,
                                    blank_text='กรุณาเลือกผลผลิต')
    borrower = QuerySelectField(query_factory=lambda: StaffAccount.get_active_accounts(), get_label='fullname',
                                allow_blank=True, blank_text='กรุณาเลือกผู้ใช้เงินทดรองจ่าย')


class ComplaintCommitteeForm(ModelForm):
    class Meta:
        model = ComplaintCommittee

    id = HiddenField()
    staff = QuerySelectField(query_factory=lambda: StaffAccount.get_active_accounts(), get_label='fullname',
                                allow_blank=True, blank_text='กรุณาเลือกรายชื่อคณะกรรมการ')


class ComplaintCommitteeGroupForm(ModelForm):
    class Meta:
        model = ComplaintCommittee
    committees = FieldList(FormField(ComplaintCommitteeForm, ComplaintCommittee))