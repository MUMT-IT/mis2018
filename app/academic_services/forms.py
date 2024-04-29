from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, SubmitField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo
from wtforms_alchemy import model_form_factory
from app.academic_services.models import *
from app.staff.models import StaffAccount, StaffCustomerInfo

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


class StaffCustomerAccountForm(ModelForm):
    class Meta:
        model = StaffAccount


class StaffCustomerInfoForm(ModelForm):
    class Meta:
        model = StaffCustomerInfo

    # account = FieldList(FormField(StaffCustomerAccountForm, default=StaffAccount), min_entries=1)