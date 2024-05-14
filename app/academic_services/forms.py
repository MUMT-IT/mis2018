from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, SubmitField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo
from wtforms_alchemy import model_form_factory, QuerySelectField
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


class QuerySelectFieldAppendable(QuerySelectField):
    def __init__(self, label, validators=None, **kwargs):
        super(QuerySelectFieldAppendable, self).__init__(label, validators, **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            if self.allow_blank and valuelist[0] == '__None':
                self.data = None
            else:
                self._data = None
                value = valuelist[0]
                if not value.isdigit():
                    organization = ServiceCustomerOrganization.query.filter_by(organization_name=value).first()
                    if not organization:
                        organization = ServiceCustomerOrganization(organization_name=value)
                        db.session.add(organization)
                        db.session.commit()
                    self._formdata = str(organization.id)
                else:
                    self._formdata = value


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo


class ServiceCustomerOrganizationForm(ModelForm):
    class Meta:
        model = ServiceCustomerOrganization