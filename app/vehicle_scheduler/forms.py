from wtforms import ValidationError
from wtforms.validators import InputRequired

from app.forms import MyDateTimePickerField

from app.main import db
from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.models import IOCode
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
    vehicle = QuerySelectField('Vehicle', query_factory=lambda: VehicleResource.query.all(),
                                get_label='license', blank_text='Select a vehicle..', allow_blank=False)
    iocode = QuerySelectField('IO Code', query_factory=lambda: IOCode.query.all())
    start = MyDateTimePickerField('Start', validators=[InputRequired()])
    end = MyDateTimePickerField('End', validators=[InputRequired()])

    def validate_init_milage(form, field):
        if field.data and form.end_milage.data:
            if field.data > form.end_milage.data:
                raise ValidationError('Initial mileage must be less than the end mileage.')
