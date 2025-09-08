flask_wtf
from wtforms import StringField, SelectField, TextAreaField, DateField, TimeField, IntegerField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import TextArea
from app.models import EventType

class EventForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=100)])
    event_type = SelectField('Event Type', choices=[(et.id, et.name) for et in EventType.query.all()], validators=[DataRequired()])
    description = TextAreaField('Description', widget=TextArea(), validators=[Optional()])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    start_time = TimeField('Start Time', format='%H:%M', validators=[DataRequired()])
    duration = IntegerField('Duration (minutes)', validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired(), Length(max=200)])
