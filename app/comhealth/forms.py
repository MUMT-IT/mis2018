from flask_wtf import FlaskForm
from wtforms import StringField, DateField
from wtforms.validators import DataRequired


class ScheduleForm(FlaskForm):
    location = StringField('Location', validators=[DataRequired()])
    service_date = StringField('Service Date', validators=[DataRequired()])