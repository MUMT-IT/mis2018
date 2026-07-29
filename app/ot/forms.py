# -*- coding:utf-8 -*-
from wtforms.validators import DataRequired

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, SelectField, DateField, FieldList, FormField, StringField, RadioField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.ot.models import *
from app.models import Org

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class OtAnnouncementSignatoryForm(FlaskForm):
    class Meta:
        csrf = False

    report_creator_staff = QuerySelectField(u'ผู้จัดทำ',
                                            query_factory=lambda: StaffAccount.get_active_accounts(),
                                            get_label='fullname',
                                            allow_blank=True,
                                            blank_text='กรุณาเลือกรายชื่อ',
                                            validators=[DataRequired()])
    report_creator_position = StringField(u'ตำแหน่งผู้จัดทำ', validators=[DataRequired()])
    signer_staff = QuerySelectField(u'ผู้ลงนาม',
                                    query_factory=lambda: StaffAccount.get_active_accounts(),
                                    get_label='fullname',
                                    allow_blank=True,
                                    blank_text='กรุณาเลือกรายชื่อ',
                                    validators=[DataRequired()])
    signer_position = StringField(u'ตำแหน่งผู้ลงนาม', validators=[DataRequired()])


class OtPaymentAnnounceForm(ModelForm):
    class Meta:
        model = OtPaymentAnnounce
        exclude = ['upload_file_url', 'cancelled_at']
        field_args = {'topic': {'validators': [DataRequired()]},
                      'announce_at': {'validators': [DataRequired()]},
                      'start_datetime': {'validators': [DataRequired()]}}

    org = QuerySelectField(u'หน่วยงาน',
                           get_label='name',
                           query_factory=lambda: Org.query.all())
    signatories = FieldList(FormField(OtAnnouncementSignatoryForm), min_entries=0)
    upload = FileField('File Upload')


class OtCompensationRateForm(ModelForm):
    class Meta:
        model = OtCompensationRate
        exclude = ['role']

    ot_job_role = QuerySelectField(u'ตำแหน่ง',
                                   get_label='role',
                                   query_factory=lambda: OtJobRole.query.all())
    time_slot = QuerySelectField(u'ช่วงเวลา',
                                 get_label=lambda slot: f'{slot.start} - {slot.end}',
                                 query_factory=lambda: OtTimeSlot.query.all())
    announcement = QuerySelectField(u'ประกาศ',
                                    get_label='topic',
                                    query_factory=lambda: OtPaymentAnnounce.query.all())
    work_at_org = QuerySelectField(u'ปฏิบัติงานที่',
                                   get_label='name',
                                   query_factory=lambda: Org.query.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'work_for_org' in self._fields:
            self._fields.pop('work_for_org')
            if hasattr(self, 'work_for_org'):
                delattr(self, 'work_for_org')


class OtJobRoleForm(FlaskForm):
    announcement = QuerySelectField(u'ประกาศ',
                                    get_label='topic',
                                    query_factory=lambda: OtPaymentAnnounce.query.all())
    work_at_org = QuerySelectField(u'หน่วยงานที่ปฏิบัติงาน',
                                   get_label='name',
                                   query_factory=lambda: Org.query.all())
    role = StringField(u'ตำแหน่งงาน', validators=[DataRequired()])


class OtTimeSlotForm(FlaskForm):
    announcement = QuerySelectField(u'ประกาศ',
                                    get_label='topic',
                                    query_factory=lambda: OtPaymentAnnounce.query.all())
    work_for_org = QuerySelectField(u'หน่วยงาน',
                                    get_label='name',
                                    query_factory=lambda: Org.query.all())
    start = SelectField(u'เริ่มเวลา', validators=[DataRequired()])
    end = SelectField(u'สิ้นสุดเวลา', validators=[DataRequired()])
    color = RadioField(u'สี', choices=[
        ('#fac696', '#fac696'),
        ('#cce5ff', '#cce5ff'),
        ('#d4edda', '#d4edda'),
        ('#f8d7da', '#f8d7da'),
    ], validators=[DataRequired()], default='#fac696')
    note = StringField(u'หมายเหตุ')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start.choices = [(t, t) for t in time_slots]
        self.end.choices = [(t, t) for t in time_slots]


class OtDocumentApprovalForm(ModelForm):
    class Meta:
        model = OtDocumentApproval

    upload = FileField('File Upload')
    # cost_center = QuerySelectField(get_label='id',
    #                                query_factory=lambda: CostCenter.query.all())
    # io = QuerySelectField(get_label='id',
    #                        query_factory=lambda: IOCode.query.all())


time_slots = []
for hour in range(0, 24):
    for minute in (0, 30):
        time_slots.append('{:02d}:{:02d}'.format(hour, minute))


def get_compensation_rates_for_timeslot(timeslot):
    rates = OtCompensationRate.query.filter_by(timeslot_id=timeslot.id).all()
    if rates:
        return rates
    return OtCompensationRate.query.filter_by(
        announce_id=timeslot.announcement_id,
        work_at_org_id=timeslot.work_for_org_id,
    ).all()


def create_ot_record_form(slot_key, work_at_org_id=None):
    def compensation_query():
        if getattr(slot_key, 'id', None):
            return get_compensation_rates_for_timeslot(slot_key)
        elif isinstance(slot_key, (list, tuple, set)):
            return OtCompensationRate.query.filter(OtCompensationRate.announce_id.in_(slot_key))
        else:
            return OtCompensationRate.query.filter_by(timeslot_id=slot_key).all()

    class OtRecordForm(ModelForm):
        class Meta:
            model = OtRecord

        compensation = QuerySelectField('หน้าที่และอัตรา',
                                        get_label='dropdown_label',
                                        query_factory=compensation_query,
                                        allow_blank=False)
        staff = SelectMultipleField('บุคลากร', coerce=int)

    return OtRecordForm


class OtScheduleItemForm(FlaskForm):
    compensation = SelectField('เวร', validate_choice=False)

    time_slots = SelectMultipleField('ช่วงเวลา', validate_choice=False,
                                     widget=ListWidget(prefix_label=False),
                                     option_widget=CheckboxInput())
    staff = SelectMultipleField('บุคลากร', coerce=int)


class OtScheduleForm(FlaskForm):
    date = DateField('วันที่', validators=[DataRequired()])

    role = SelectField('ตำแหน่ง', validate_choice=False)

    items = FieldList(FormField(OtScheduleItemForm), min_entries=0)
