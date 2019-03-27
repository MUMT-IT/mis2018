from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, IntegerField, HiddenField
from wtforms.validators import DataRequired


class ServiceForm(FlaskForm):
    location = StringField('Location', validators=[DataRequired()])
    service_date = StringField('Service Date', validators=[DataRequired()])


class TestProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    desc = StringField('Description', validators=[DataRequired()])
    age_max = IntegerField('Age max')
    age_min = IntegerField('Age min')
    gender = SelectField('Gender', choices=[(0, 'Female'),
                                            (1, 'Male'),
                                            (2, 'All')],
                         default=2, coerce=int)


class TestListForm(FlaskForm):
    set_id = HiddenField('Set ID', validators=[DataRequired()])
    test_list = HiddenField('Test List', validators=[DataRequired()])
