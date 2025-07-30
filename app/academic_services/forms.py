from flask_wtf import FlaskForm
from wtforms import DecimalField, FormField, StringField, BooleanField, TextAreaField, DateField, SelectField, \
    SelectMultipleField, HiddenField, PasswordField, SubmitField, widgets, RadioField, FieldList, FileField, FloatField
from wtforms.validators import DataRequired, EqualTo, Length
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
    submit = SubmitField('เข้าสู่ระบบ')


class ForgetPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Submit')


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Submit')


class ServiceCustomerContactForm(ModelForm):
    class Meta:
        model = ServiceCustomerContact


class ServiceCustomerAddressForm(ModelForm):
    class Meta:
        model = ServiceCustomerAddress

    province = QuerySelectField('จังหวัด', query_factory=lambda: Province.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกจังหวัด', get_label='name')
    district = QuerySelectField('เขต/อำเภอ', query_factory=lambda: District.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกเขต/อำเภอ', get_label='name')
    subdistrict = QuerySelectField('แขวง/ตำบล', query_factory=lambda: Subdistrict.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกแขวง/ตำบล', get_label='name')


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    type = QuerySelectField('ประเภท', query_factory=lambda: ServiceCustomerType.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกประเภท', get_label='type')
    customer_contacts = FieldList(FormField(ServiceCustomerContactForm, default=ServiceCustomerContact), min_entries=1)


class ServiceCustomerAccountForm(ModelForm):
    class Meta:
        model = ServiceCustomerAccount

    password = PasswordField('Password', validators=[DataRequired(),
                                                     Length(min=8, message='รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร')])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password',
                                                                                             message='รหัสผ่านไม่ตรงกัน')])


class CheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


field_types = {
    'string': FieldTuple(StringField, 'input is-expanded'),
    'text': FieldTuple(TextAreaField, 'textarea'),
    'number': FieldTuple(FloatField, 'input is-expanded'),
    'boolean': FieldTuple(BooleanField, ''),
    'date': FieldTuple(StringField, 'input'),
    'choice': FieldTuple(RadioField, ''),
    'multichoice': FieldTuple(CheckboxField, 'checkbox')
}


def create_field(field):
    _field = field_types[field['fieldType']]
    _field_label = f"{field['fieldLabel']}"
    _field_placeholder = f"{field['fieldPlaceHolder']}"
    if field['fieldType'] == 'choice' or field['fieldType'] == 'multichoice':
        choices = field['items'].split(', ') if field['items'] else field['fieldChoice'].split(', ')
        return _field.type_(label=_field_label,
                            choices=[(c, c) for c in choices],
                            render_kw={'class': _field.class_,
                                       'placeholder': _field_placeholder})
    elif field['fieldType'] == 'date':
        return _field.type_(label=_field_label,
                            render_kw={'class': _field.class_,
                                       'placeholder': _field_placeholder,
                                       'type': 'date'})
    else:
        if field['fieldDefault']:
            default_value = field['fieldDefault']
        else:
            default_value = None
        return _field.type_(label=_field_label,
                            default=default_value,
                            render_kw={'class': _field.class_,
                                       'placeholder': _field_placeholder})


def create_field_group_form_factory(field_group):
    class GroupForm(FlaskForm):
        subform_fields = {}
        _subform_field = None
        _subform_field_name = None
        for field in field_group:
            _field = create_field(field)
            if field['formFieldName']:
                _subform_field_name = field['formFieldName']
                _subform_field, _ = subform_fields.get(_subform_field_name, (None, None))
                if _subform_field is None:
                    _subform_field = type(_subform_field_name, (FlaskForm,), {})
                    min_entries = field['formFieldMinEntries'] if isinstance(field['formFieldMinEntries'], int) else\
                        len(field['formFieldMinEntries'].split(', '))
                    subform_fields[_subform_field_name] = (_subform_field, min_entries)
                setattr(_subform_field, field['fieldName'], _field)
            else:
                if _subform_field_name:
                    _subform_field, min_entries = subform_fields.get(_subform_field_name)
                    vars()[f'{_subform_field_name}'] = FieldList(FormField(_subform_field, label=field['formFieldLabel']), min_entries=min_entries)
                    _subform_field_name = None
                vars()[f'{field["fieldName"]}'] = _field
        if _subform_field_name:
            _subform_field, min_entries = subform_fields.get(_subform_field_name)
            vars()[f'{_subform_field_name}'] = FieldList(FormField(_subform_field, label=field['formFieldLabel']), min_entries=min_entries)
    return GroupForm


def create_request_form(table):
    field_groups = defaultdict(list)
    for idx, row in table.iterrows():
        field_group_key = row['fieldGroupParent'] if row['fieldGroupParent'] else row['fieldGroup']
        field_groups[field_group_key].append(row)

    class MainForm(FlaskForm):
        for group_name, field_group in field_groups.items():
            vars()[f"{group_name}"] = FormField(create_field_group_form_factory(field_group))
        vars()["csrf_token"] = HiddenField(default=generate_csrf())
        vars()['submit'] = SubmitField('บันทึกและดำเนินการต่อ', render_kw={'class': 'button is-success',
                                                            'style': 'display: block; margin: 0 auto; margin-top: 1em'})
    return MainForm


class ServiceRequestForm(ModelForm):
    class Meta:
        model = ServiceRequest


class ServiceQuotationForm(ModelForm):
    class Meta:
        model = ServiceQuotation
        exclude = ['digital_signature']


class ServiceSampleForm(ModelForm):
    class Meta:
        model = ServiceSample


class ServicePaymentForm(ModelForm):
    class Meta:
        model = ServicePayment
        exclude = ['amount_due']
    file_upload = FileField('File Upload')