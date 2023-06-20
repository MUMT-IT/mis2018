# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms.validators import InputRequired
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.forms import MyDateTimePickerField
from app.instruments.models import InstrumentsBooking
from app.main import db

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class InstrumentsBookingForm(ModelForm):
    class Meta:
        model = InstrumentsBooking
        exclude = [
            'created_at',
            'updated_at',
            'cancelled_at'
        ]
    start = MyDateTimePickerField(u'เริ่มต้น', validators=[InputRequired()])
    end = MyDateTimePickerField(u'สิ้นสุด', validators=[InputRequired()])

