from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, SubmitField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo
from wtforms_alchemy import model_form_factory
from app.academic_services.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log in')


class ForgetPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Submit')


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Submit')


class ServiceCustomerAccountForm(ModelForm):
    class Meta:
        model = ServiceCustomerAccount


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo


class ServiceEditCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    staff_account = FieldList(FormField(ServiceCustomerAccountForm, default=ServiceCustomerAccount), min_entries=1)
