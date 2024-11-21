from flask_wtf import FlaskForm
from wtforms import DecimalField, FormField, StringField, BooleanField, TextAreaField, DateField, SelectField, \
    SelectMultipleField, HiddenField, PasswordField, SubmitField, widgets, RadioField, FieldList, FileField
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


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    same_address = BooleanField('ใช้ข้อมูลเดียวกับที่อยู่ใบเสนอราคา')
    type = QuerySelectField('ประเภท', query_factory=lambda: ServiceCustomerType.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกประเภท', get_label='type')


class ServiceCustomerAccountForm(ModelForm):
    class Meta:
        model = ServiceCustomerAccount

    customer_info = FormField(ServiceCustomerInfoForm, default=ServiceCustomerInfo)
    password = PasswordField('Password', validators=[DataRequired(),
                                                     Length(min=8, message='รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร')])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password',
                                                                                             message='รหัสผ่านไม่ตรงกัน')])


class CheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


field_types = {
    'string': FieldTuple(StringField, 'input'),
    'text': FieldTuple(TextAreaField, 'textarea'),
    'number': FieldTuple(DecimalField, 'input'),
    'boolean': FieldTuple(BooleanField, ''),
    'date': FieldTuple(DateField, 'input'),
    'choice': FieldTuple(RadioField, ''),
    'multichoice': FieldTuple(CheckboxField, 'checkbox')
}

_i = 0


def create_field(field):
    global _i
    _field = field_types[field['fieldType']]
    _field_label = f"{field['fieldLabel']}"
    _field_placeholder = f"{field['fieldPlaceHolder']}"
    if field['fieldType'] == 'choice' or field['fieldType'] == 'multichoice':
        choices = field['items'].split(', ') if field['items'] else field['fieldChoice'].split(', ')
        return _field.type_(label=_field_label,
                            choices=[(c, c) for c in choices],
                            render_kw={'class': _field.class_,
                                       'placeholder': _field_placeholder})
    else:
        value_items = None
        if field['items']:
            items = field['items'].split(', ')
            if _i < len(items):
                value_items = items[_i]
                _i += 1
        return _field.type_(label=_field_label,
                            default=value_items,
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
                    vars()[f'{_subform_field_name}'] = FieldList(FormField(_subform_field), min_entries=min_entries)
                    _subform_field_name = None
                vars()[f'{field["fieldName"]}'] = _field
        if _subform_field_name:
            _subform_field, min_entries = subform_fields.get(_subform_field_name)
            vars()[f'{_subform_field_name}'] = FieldList(FormField(_subform_field), min_entries=min_entries)
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
        vars()['submit'] = SubmitField('Submit', render_kw={'class': 'button is-success',
                                                            'style': 'display: block; margin: 0 auto; margin-top: 1em'})
    return MainForm


class ServiceRequestForm(ModelForm):
    class Meta:
        model = ServiceRequest


class ServiceCustomerContactForm(ModelForm):
    class Meta:
        model = ServiceCustomerContact

    type = QuerySelectField('ประเภท', query_factory=lambda: ServiceCustomerContactType.query.all(), allow_blank=True,
                            blank_text='กรุณาเลือกประเภท', get_label='type')


class ServiceCustomerAddressForm(ModelForm):
    class Meta:
        model = ServiceCustomerAddress


def create_payment_form(file=None):
    class ServicePaymentForm(ModelForm):
        class Meta:
            model = ServicePayment
            if file:
                exclude = ['amount_paid']
        if file:
            file_upload = FileField('File Upload')
    return ServicePaymentForm


class ServiceResultForm(ModelForm):
    class Meta:
        model = ServiceResult


class ServiceQuotationForm(ModelForm):
    class Meta:
        model = ServiceQuotation


class ServiceInvoiceForm(ModelForm):
    class Meta:
        model = ServiceInvoice