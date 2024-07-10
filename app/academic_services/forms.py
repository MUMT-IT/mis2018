from flask_wtf import FlaskForm
from wtforms import DecimalField, FormField, StringField, BooleanField, TextAreaField, DateField, SelectField, \
    SelectMultipleField, HiddenField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.academic_services.models import *
from flask_login import current_user
from collections import defaultdict, namedtuple
from flask_wtf.csrf import generate_csrf
import gspread

FieldTuple = namedtuple('FieldTuple', ['type_', 'class_'])
BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log in')


class ForgetPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Submit')


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Submit')


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
                        organization = ServiceCustomerOrganization(organization_name=value,
                                                                   creator_id=current_user.customer_info.id)
                        db.session.add(organization)
                        db.session.commit()
                    self._formdata = str(organization.id)
                else:
                    self._formdata = value


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo
    organization = QuerySelectFieldAppendable('บริษัทหรือองค์กร', query_factory=lambda: ServiceCustomerOrganization.query.all(),
                                              allow_blank=True, blank_text='กรุณาเลือกบริษัทหรือองค์กร', get_label='organization_name')


class ServiceCustomerAccountForm(ModelForm):
    class Meta:
        model = ServiceCustomerAccount
    customer_info = FormField(ServiceCustomerInfoForm, default=ServiceCustomerInfo)
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password',
                                                                                             message='รหัสผ่านไม่ตรงกัน')])


class ServiceCustomerOrganizationForm(ModelForm):
    class Meta:
        model = ServiceCustomerOrganization