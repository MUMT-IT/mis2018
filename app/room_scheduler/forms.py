from datetime import datetime

from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import Field, IntegerField, StringField, TextAreaField, TimeField
from wtforms.validators import DataRequired, NumberRange, Optional
from wtforms.widgets import TextInput
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from app.room_scheduler.models import *
from app.staff.models import StaffAccount, StaffGroupDetail

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


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
    conjoined_rooms = QuerySelectMultipleField(
        'ห้องที่เชื่อมต่อกัน',
        query_factory=lambda: RoomResource.query.order_by(
            RoomResource.location, RoomResource.number
        ).all(),
        get_label=lambda room: '{} — {}'.format(room.number, room.location),
    )
