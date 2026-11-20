from datetime import datetime

from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import Field, IntegerField, StringField, TextAreaField, TimeField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError
from wtforms.widgets import TextInput
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from app.models import IOCode
from app.room_scheduler.models import *
from app.staff.models import StaffAccount, StaffGroupDetail

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class QuerySelectFieldRequired(QuerySelectField):
    def iter_choices(self):
        for value, label, selected in super().iter_choices():
            if value == '__None':
                yield '', label, selected
            else:
                yield value, label, selected

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0] == '':
            valuelist = ['__None']
        return super().process_formdata(valuelist)


def _required_when_refreshment_requested(message):
    def validate(form, field):
        if form.is_refreshment.data and not field.data:
            raise ValidationError(message)
    return validate


class DateTimePickerField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return self.data.strftime('%d-%m-%Y %H:%M:%S')
        else:
            return ''

    def process_formdata(self, value):
        if value[0]:
            self.data = datetime.strptime(value[0], '%d-%m-%Y %H:%M:%S')
        else:
            self.data = None


class RoomEventForm(ModelForm):
    class Meta:
        model = RoomEvent
        exclude = ['end']

    start = DateTimePickerField('เริ่มต้น')
    end = DateTimePickerField('สิ้นสุด')

    category = QuerySelectField(query_factory=lambda: EventCategory.query.all())
    participants = QuerySelectMultipleField(query_factory=lambda: StaffAccount.query.filter(
                                 StaffAccount.personal_info.has(retired=False)).all(), get_label='fullname')
    cost_center = QuerySelectFieldRequired(
        query_factory=lambda: CostCenter.query.all(),
        get_label='id',
        allow_blank=True,
        blank_text='กรุณาเลือกรหัสศูนย์ต้นทุน',
        validators=[_required_when_refreshment_requested('กรุณาเลือกรหัสศูนย์ต้นทุน')],
    )
    iocode = QuerySelectFieldRequired(
        query_factory=lambda: IOCode.query.all(),
        get_label='id',
        allow_blank=True,
        blank_text='กรุณาเลือกรหัสใบสั่งงานภายใน',
        validators=[_required_when_refreshment_requested('กรุณาเลือกรหัสใบสั่งงานภายใน')],
    )
    product_code = QuerySelectFieldRequired(
        query_factory=lambda: ProductCode.query.all(),
        get_label='product_code',
        allow_blank=True,
        blank_text='กรุณาเลือกผลผลิต',
        validators=[_required_when_refreshment_requested('กรุณาเลือกผลผลิต / หมวดค่าใช้จ่าย')],
    )


class RoomParticipantListForm(ModelForm):
    class Meta:
        model = RoomEvent
        exclude = ['title', 'start', 'end']

    cost_center = QuerySelectField(query_factory=lambda: CostCenter.query.all(), get_label='id',
                                   allow_blank=True, blank_text='กรุณาเลือกรหัสศูนย์ต้นทุน',
                                   validators=[DataRequired(message='กรุณาเลือกรหัสศูนย์ต้นทุน')],
                                   render_kw={'required': True})
    iocode = QuerySelectField(query_factory=lambda: IOCode.query.all(), get_label='id', allow_blank=True,
                               blank_text='กรุณาเลือกรหัสใบสั่งงานภายใน',
                               validators=[DataRequired(message='กรุณาเลือกรหัสใบสั่งงานภายใน')],
                               render_kw={'required': True})
    product_code = QuerySelectField(query_factory=lambda: ProductCode.query.all(), get_label='product_code',
                                    allow_blank=True, blank_text='กรุณาเลือกผลผลิต',
                                    validators=[DataRequired(message='กรุณาเลือกผลผลิต / หมวดค่าใช้จ่าย')],
                                    render_kw={'required': True})


class RoomAdminForm(FlaskForm):
    number = StringField('หมายเลขห้อง', validators=[DataRequired()])
    location = StringField('วิทยาเขต', validators=[DataRequired()])
    floor = StringField('ชั้น', validators=[Optional()])
    occupancy = IntegerField(
        'ความจุ', validators=[DataRequired(), NumberRange(min=1)]
    )
    desc = TextAreaField('รายละเอียด', validators=[Optional()])
    business_hour_start = TimeField('เวลาเปิด', validators=[Optional()])
    business_hour_end = TimeField('เวลาปิด', validators=[Optional()])
    availability = QuerySelectField(
        'ความพร้อมใช้',
        query_factory=lambda: RoomAvailability.query.order_by(RoomAvailability.availability).all(),
        allow_blank=True,
        blank_text='ไม่ระบุ',
    )
    type = QuerySelectField(
        'ประเภทห้อง',
        query_factory=lambda: RoomType.query.order_by(RoomType.type).all(),
        allow_blank=True,
        blank_text='ไม่ระบุ',
    )
    coordinators = QuerySelectMultipleField(
        'ผู้ประสานงาน',
        query_factory=lambda: StaffAccount.get_active_accounts(),
        get_label='fullname',
    )
    conjoined_rooms = QuerySelectMultipleField(
        'ห้องที่เชื่อมต่อกัน',
        query_factory=lambda: RoomResource.query.order_by(
            RoomResource.location, RoomResource.number
        ).all(),
        get_label=lambda room: '{} — {}'.format(room.number, room.location),
    )
