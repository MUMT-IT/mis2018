# -*- coding:utf-8 -*-
from wtforms import ValidationError
from wtforms.validators import InputRequired

from app.forms import MyDateTimePickerField

from app.main import db
from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.models import IOCode, Org
from app.vehicle_scheduler.models import VehicleBooking, VehicleResource

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class VehicleBookingForm(ModelForm):
    class Meta:
        model = VehicleBooking
        exclude = [
            'created_at',
            'updated_at',
            'cancelled_at',
            'approved_at',
            'closed',
            'approved',
            'init_location',
        ]
    vehicle = QuerySelectField(u'พาหนะ', query_factory=lambda: VehicleResource.query.all(),
                                get_label='license', blank_text='Select a vehicle..', allow_blank=False)
    org = QuerySelectField(u'หน่วยงาน', query_factory=lambda: Org.query.all(),
                               get_label='name', blank_text='Select a org..', allow_blank=False)
    iocode = QuerySelectField('IO Code', query_factory=lambda: IOCode.query.all())
    start = MyDateTimePickerField(u'เริ่มต้น', validators=[InputRequired()])
    end = MyDateTimePickerField(u'สิ้นสุด', validators=[InputRequired()])

    def validate_init_milage(form, field):
        if field.data and form.end_milage.data:
            if field.data > form.end_milage.data:
                raise ValidationError(u'เลขไมล์ไม่ถูกต้อง กรุณาตรวจสอบ')

    def validate_start(form, field):
        if field.data and form.end.data:
            if field.data >= form.end.data:
                raise ValidationError(u'ระบุวันและเวลาเริ่มต้นสิ้นสุดไม่ถูกต้อง')
