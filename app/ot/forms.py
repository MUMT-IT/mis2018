# -*- coding:utf-8 -*-
from wtforms.validators import DataRequired

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, SelectField, DateField, FieldList, FormField, StringField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.ot.models import *
from app.models import Org

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


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
    work_at_org = QuerySelectField(get_label='name',
                                   query_factory=lambda: Org.query.all())
    work_for_org = QuerySelectField(u'หน่วยงาน',
                                    get_label='name',
                                    query_factory=lambda: Org.query.all())


class OtTimeSlotForm(FlaskForm):
    announcement = QuerySelectField(u'ประกาศ',
                                    get_label='topic',
                                    query_factory=lambda: OtPaymentAnnounce.query.all())
    work_for_org = QuerySelectField(u'หน่วยงาน',
                                    get_label='name',
                                    query_factory=lambda: Org.query.all())
    start = SelectField(u'เริ่มเวลา', validators=[DataRequired()])
    end = SelectField(u'สิ้นสุดเวลา', validators=[DataRequired()])
    color = StringField(u'สี')
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


def create_ot_record_form(slot_id):
    class OtRecordForm(ModelForm):
        class Meta:
            model = OtRecord

        compensation = QuerySelectField('หน้าที่และอัตรา',
                                        query_factory=lambda: OtCompensationRate.query.filter_by(timeslot_id=slot_id),
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
