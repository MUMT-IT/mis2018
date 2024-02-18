from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, IntegerField, HiddenField, FloatField, PasswordField, \
    TextAreaField
from wtforms.validators import DataRequired, optional
from wtforms_alchemy import model_form_factory, QuerySelectField
from wtforms_components import EmailField

from app.comhealth.models import ComHealthTest, ComHealthContainer, ComHealthDepartment, ComHealthDivision
from app.main import db

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ServiceForm(FlaskForm):
    location = StringField('Location', validators=[DataRequired()])
    service_date = DateField('Service Date', validators=[DataRequired()])


class TestProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    desc = StringField('Description', validators=[DataRequired()])
    age_max = IntegerField('Age max', validators=[optional()])
    age_min = IntegerField('Age min', validators=[optional()])
    gender = SelectField('Gender', choices=[(0, 'Female'),
                                            (1, 'Male'),
                                            (2, 'All')],
                         default=2, coerce=int)
    quote = FloatField('Quote', validators=[optional()])


class TestGroupForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    desc = StringField('Description', validators=[DataRequired()])
    age_max = IntegerField('Age max', validators=[optional()])
    age_min = IntegerField('Age min', validators=[optional()])
    gender = SelectField('Gender', choices=[(0, 'Female'),
                                            (1, 'Male'),
                                            (2, 'All')],
                         default=2, coerce=int)


class TestListForm(FlaskForm):
    set_id = HiddenField('Set ID', validators=[DataRequired()])
    test_list = HiddenField('Test List', validators=[DataRequired()])


class TestForm(ModelForm):
    class Meta:
        model = ComHealthTest
    container = QuerySelectField('Container',
                                 query_factory=lambda: ComHealthContainer.query.all(),
                                 allow_blank=True, blank_text='กรุณาระบุภาชนะ')


class CustomerForm(FlaskForm):
    org_id = HiddenField('org_id')
    service_id = HiddenField('service_id')
    title = StringField('Title')
    firstname = StringField('First Name')
    lastname = StringField('Last Name')
    dob = StringField('Date of Birth', validators=[optional()])
    age = IntegerField('Age', validators=[optional()])
    gender = SelectField('Gender', choices=[(0, 'Female'), (1, 'Male')],
                         coerce=int, default=0)
    phone = StringField('Phone', validators=[optional()])
    emptype = SelectField('Employment Type', validators=[DataRequired()], coerce=int)
    emp_id  = StringField('Employee ID', validators=[optional()])
    email =  StringField('Email', validators=[optional()])
    dept = QuerySelectField('Deparment', validators=[optional()],
                            query_factory=lambda: ComHealthDepartment.query.all())
    division = QuerySelectField('Division', validators=[optional()],
                            query_factory=lambda: ComHealthDivision.query.all())
    unit = StringField('Unit', validators=[optional()])


class CustomerInfoForm(FlaskForm):
    gender = SelectField('Gender', choices=[(0, 'หญิง/Female'), (1, 'ชาย/Male')], coerce=int, default=0)
    phone = StringField('Phone', validators=[optional()])
    email =  StringField('Email', validators=[optional()])


class PasswordOfSignDigitalForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    cancel_comment = TextAreaField('cancel_comment', validators=[DataRequired()])


class SendMailToCustomerForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired()])