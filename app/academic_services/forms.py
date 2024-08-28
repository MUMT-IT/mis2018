from flask_wtf import FlaskForm
from wtforms import DecimalField, FormField, StringField, BooleanField, TextAreaField, DateField, SelectField, \
    SelectMultipleField, HiddenField, PasswordField, SubmitField, widgets, RadioField
from wtforms.validators import DataRequired, EqualTo
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.academic_services.models import *
from flask_login import current_user
from collections import defaultdict, namedtuple
from flask_wtf.csrf import generate_csrf

FieldTuple = namedtuple('FieldTuple', ['type_', 'class_'])
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
                        if current_user.is_authenticated:
                            if hasattr(current_user, 'customer_info'):
                                organization = ServiceCustomerOrganization(organization_name=value,
                                                                           creator_id=current_user.customer_info.id)
                            elif hasattr(current_user, 'personal_info'):
                                organization = ServiceCustomerOrganization(organization_name=value,
                                                                           admin_id=current_user.personal_info.id)
                        db.session.add(organization)
                        db.session.commit()
                    self._formdata = str(organization.id)
                else:
                    self._formdata = value


class ServiceCustomerOrganizationForm(ModelForm):
    class Meta:
        model = ServiceCustomerOrganization


def create_customer_form(type=None):
    class ServiceCustomerInfoForm(ModelForm):
        class Meta:
            model = ServiceCustomerInfo
        if type == 'select':
            organization = QuerySelectFieldAppendable('บริษัท/องค์กร/โครงการ', query_factory=lambda: ServiceCustomerOrganization.query.all(),
                                                      allow_blank=True, blank_text='กรุณาเลือกบริษัท/องค์กร/โครงการ', get_label='organization_name')
        elif type == 'form':
            organization = FormField(ServiceCustomerOrganizationForm, default=ServiceCustomerOrganization)
    return ServiceCustomerInfoForm


class ServiceCustomerAccountForm(ModelForm):
    class Meta:
        model = ServiceCustomerAccount
    customer_info = FormField(create_customer_form(type=None), default=ServiceCustomerInfo)
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password',
                                                                                             message='รหัสผ่านไม่ตรงกัน')])


class CheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


def custom_string_input(field, ul_class="", **kwargs):
    return f'''<div class="field">
    <div class="control">
    <input id="{field.id}" class="input" type="string" name="{field.name}" placeholder="custom input">
    </div>
    </div>'''


class CustomStringField(StringField):
    widget = custom_string_input


field_types = {
    'string': FieldTuple(StringField, 'input'),
    'text': FieldTuple(TextAreaField, 'textarea'),
    'number': FieldTuple(DecimalField, 'input'),
    'boolean': FieldTuple(BooleanField, ''),
    'date': FieldTuple(DateField, 'input'),
    'choice': FieldTuple(RadioField, ''),
    'multichoice': FieldTuple(CheckboxField, 'checkbox')
  }


def create_field_group_form_factory(field_group):
    class GroupForm(FlaskForm):
        form_html = ''
        for field in field_group:
            _field = field_types[field['fieldType']]
            _field_type = f"{field['fieldType']}"
            _field_label = f"{field['fieldLabel']}"
            _field_placeholder = f"{field['fieldPlaceHolder']}"
            if field['fieldType'] == 'choice' or field['fieldType'] == 'multichoice':
                choices = field['items'].split(', ') if field['items'] else field['fieldChoice'].split(', ')
                vars()[f"{field['fieldName']}"] = _field.type_(label=_field_label,
                                                               choices=[(c, c) for c in choices],
                                                               render_kw={'class': _field.class_,
                                                                          'placeholder': _field_placeholder})
            else:
                vars()[f"{field['fieldName']}"] = _field.type_(label=_field_label, render_kw={'class': _field.class_,
                                                                                              'placeholder': _field_placeholder})
    return GroupForm


def create_request_form(table):
    field_groups = defaultdict(list)
    for idx,row in table.iterrows():
        field_groups[row['fieldGroup']].append(row)

    class MainForm(FlaskForm):
        for group_name, field_group in field_groups.items():
            vars()[f"{group_name}"] = FormField(create_field_group_form_factory(field_group))
        vars()["csrf_token"] = HiddenField(default=generate_csrf())
        vars()['submit'] = SubmitField('Submit', render_kw={'class': 'button is-success',
                                                            'style': 'display: block; margin: 0 auto;'})
    return MainForm
