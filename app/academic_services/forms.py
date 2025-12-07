from flask_wtf import FlaskForm
from wtforms import (FormField, BooleanField, TextAreaField, SelectField, SelectMultipleField, HiddenField,
                     PasswordField,
                     SubmitField, widgets, RadioField, FieldList, FileField, FloatField, IntegerField, StringField)
from wtforms.validators import DataRequired, EqualTo, Length, Optional
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.academic_services.models import *
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

    contact_name = StringField('ชื่อผู้ประสานงาน', validators=[DataRequired()])
    phone_number = StringField('เบอร์โทรศัพท์', validators=[DataRequired()])
    email = StringField('อีเมล', validators=[DataRequired()])


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    type = QuerySelectField('ประเภท', query_factory=lambda: ServiceCustomerType.query.all(), allow_blank=True,
                            blank_text='กรุณาเลือกประเภท', get_label='type',
                            validators=[DataRequired(message='กรุณาเลือกประเภท')])
    cus_name = StringField(validators=[DataRequired()])
    taxpayer_identification_no = StringField('เลขประจำตัวผู้เสียภาษีอากร', validators=[DataRequired()])
    phone_number = StringField('เบอร์โทรศัพท์', validators=[DataRequired()])
    customer_contacts = FieldList(FormField(ServiceCustomerContactForm, default=ServiceCustomerContact), min_entries=1)


class ServiceCustomerAddressForm(ModelForm):
    class Meta:
        model = ServiceCustomerAddress

    name = StringField(validators=[DataRequired()])
    address = StringField('ที่อยู่', validators=[DataRequired()])
    province = QuerySelectField('จังหวัด', query_factory=lambda: Province.query.order_by(Province.name),
                                allow_blank=True,
                                blank_text='กรุณาเลือกจังหวัด', get_label='name',
                                validators=[DataRequired(message='กรุณาเลือกจังหวัด')])
    district = QuerySelectField('เขต/อำเภอ', query_factory=lambda: [], allow_blank=True,
                                blank_text='กรุณาเลือกเขต/อำเภอ', get_label='name',
                                validators=[DataRequired(message='กรุณาเลือกเขต/อำเภอ')])
    subdistrict = QuerySelectField('แขวง/ตำบล', query_factory=lambda: [], allow_blank=True,
                                   blank_text='กรุณาเลือกแขวง/ตำบล', get_label='name',
                                   validators=[DataRequired(message='กรุณาเลือกแขวง/ตำบล')])
    zipcode = StringField('รหัสไปรษณีย์', validators=[DataRequired()])
    phone_number = StringField('เบอร์โทรศัพท์', validators=[DataRequired()])


class ServiceCustomerAccountForm(ModelForm):
    class Meta:
        model = ServiceCustomerAccount

    password = PasswordField('Password', validators=[DataRequired(),
                                                     Length(min=8,
                                                            message='รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร')])
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
    # _field_required = f"{field['require']}"
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
                                       'placeholder': _field_placeholder
                                       })


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
                    min_entries = field['formFieldMinEntries'] if isinstance(field['formFieldMinEntries'], int) else \
                        len(field['formFieldMinEntries'].split(', '))
                    subform_fields[_subform_field_name] = (_subform_field, min_entries)
                setattr(_subform_field, field['fieldName'], _field)
            else:
                if _subform_field_name:
                    _subform_field, min_entries = subform_fields.get(_subform_field_name)
                    vars()[f'{_subform_field_name}'] = FieldList(
                        FormField(_subform_field, label=field['formFieldLabel']), min_entries=min_entries)
                    _subform_field_name = None
                vars()[f'{field["fieldName"]}'] = _field
        if _subform_field_name:
            _subform_field, min_entries = subform_fields.get(_subform_field_name)
            vars()[f'{_subform_field_name}'] = FieldList(FormField(_subform_field, label=field['formFieldLabel']),
                                                         min_entries=min_entries)

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


bacteria_liquid_organisms = [
    'S. aureus ATCC 6538',
    'S. choleraesuis ATCC 10708',
    'P. aeruginosa ATCC 15442',
    'T. mentagrophytes'
]

bacteria_wash_organisms = [
    'S. aureus ATCC 6538',
    'K. pneumoniae ATCC 4352'
]


class BacteriaLiquidTestConditionForm(FlaskForm):
    liquid_organism = CheckboxField('เชื้อ', validators=[Optional()])
    liquid_ratio = IntegerField('อัตราส่วนเจือจางผลิตภัณฑ์', validators=[Optional()], render_kw={'class': 'input'})
    liquid_per_water = IntegerField('ต่อน้ำ', validators=[Optional()], render_kw={'class': 'input'})
    liquid_time_duration = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับเชื้อ (นาที)', validators=[Optional()],
                                        render_kw={'class': 'input'})


class BacteriaLiquidConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์',
                               default='ผลิตภัณฑ์ฆ่าเชื้อบนพื้นผิวไม่มีรูพรุนชนิดของเหลว หรือชนิดผง ที่ละลายน้้าได้',
                               render_kw={'class': 'input is-danger'})
    liquid_test_method = CheckboxField('วิธีทดสอบ', choices=[(c, c) for c in ['วิธีทดสอบ Use-Dilution 60 carriers',
                                                                              'วิธีทดสอบ Use-Dilution log (%) reduction']],
                                       validators=[Optional()])
    liquid_clean_type = RadioField('รูปแบบการทดสอบ',
                                   choices=[('ทดสอบแบบฆ่าเชื้ออย่างเดียว', 'ทดสอบแบบฆ่าเชื้ออย่างเดียว'), (
                                       'ทดสอบแบบทำความสะอาดและฆ่าเชื้อในขั้นตอนเดียว (one-step cleaner)',
                                       'ทดสอบแบบทำความสะอาดและฆ่าเชื้อในขั้นตอนเดียว (one-step cleaner)')],
                                   validators=[Optional()])
    liquid_dilution = RadioField('การเจือจาง', choices=[('เจือจาง', 'เจือจาง'), ('ไม่เจือจาง', 'ไม่เจือจาง')],
                                 validators=[Optional()])
    liquid_organism_fields = FieldList(FormField(BacteriaLiquidTestConditionForm),
                                       min_entries=len(bacteria_liquid_organisms))


class BacteriaSprayTestConditionForm(FlaskForm):
    spray_organism = CheckboxField('เชื้อ', validators=[Optional()])
    spray_ratio = IntegerField('อัตราส่วนเจือจางผลิตภัณฑ์', validators=[Optional()],
                               render_kw={'class': 'input'})
    spray_per_water = IntegerField('ต่อน้ำ', validators=[Optional()], render_kw={'class': 'input'})
    spray_distance = IntegerField('ระยะห่างในการฉีดพ่น (cm)', validators=[Optional()],
                                  render_kw={'class': 'input'})
    spray_of_time = IntegerField('ระยะเวลาฉีดพ่น (วินาที)', validators=[Optional()],
                                 render_kw={'class': 'input'})
    spray_time_duration = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับเชื้อ (นาที)',
                                       validators=[Optional()],
                                       render_kw={'class': 'input'})


class BacteriaSprayConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์',
                               default='ผลิตภัณฑ์ฆ่าเชื้อบนพื้นผิวไม่มีรูพรุนชนิดฉีดพ่นธรรมดา หรือ ฉีดพ่นอัดก๊าซ',
                               render_kw={'class': 'input is-danger'})
    spray_test_method = CheckboxField('วิธีทดสอบ',
                                      choices=[(c, c) for c in ['วิธีทดสอบ Spray germicidal assay 60 carriers',
                                                                'วิธีทดสอบ Spray germicidal assay log (%) reduction']],
                                      validators=[Optional()])
    spray_clean_type = RadioField('รูปแบบการทดสอบ',
                                  choices=[('ทดสอบแบบฆ่าเชื้ออย่างเดียว', 'ทดสอบแบบฆ่าเชื้ออย่างเดียว'), (
                                      'ทดสอบแบบทำความสะอาดและฆ่าเชื้อในขั้นตอนเดียว (one-step cleaner)',
                                      'ทดสอบแบบทำความสะอาดและฆ่าเชื้อในขั้นตอนเดียว (one-step cleaner)')],
                                  validators=[Optional()])
    spray_surface_type = RadioField('ชนิดพื้นผิว', choices=[('พื้นผิวแข็งไม่มีรูพรุน', 'พื้นผิวแข็งไม่มีรูพรุน'),
                                                            ('อื่นๆ โปรดระบุ', 'อื่นๆ โปรดระบุ')],
                                    validators=[Optional()])
    spray_surface_type_other = StringField('ระบุ', render_kw={'class': 'input'})
    spray_dilution = RadioField('การเจือจาง', choices=[('เจือจาง', 'เจือจาง'), ('ไม่เจือจาง', 'ไม่เจือจาง')],
                                validators=[Optional()])
    spray_organism_fields = FieldList(FormField(BacteriaSprayTestConditionForm),
                                      min_entries=len(bacteria_liquid_organisms))


class BacteriaSheetTestConditionForm(FlaskForm):
    sheet_organism = CheckboxField('เชื้อ', validators=[Optional()])
    sheet_time_duration = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับเชื้อ (นาที)', validators=[Optional()],
                                       render_kw={'class': 'input'})


class BacteriaSheetConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์',
                               default='ผลิตภัณฑ์ฆ่าเชื้อชนิดแผ่น',
                               render_kw={'class': 'input is-danger'})
    sheet_test_method = CheckboxField('วิธีทดสอบ', choices=[(c, c) for c in ['วิธีทดสอบ Qualitative test 60 carriers',
                                                                             'วิธีทดสอบ Quantitative test log (%) reduction']],
                                      validators=[Optional()])
    sheet_clean_type = RadioField('รูปแบบการทดสอบ',
                                  choices=[('ทดสอบแบบฆ่าเชื้ออย่างเดียว', 'ทดสอบแบบฆ่าเชื้ออย่างเดียว'), (
                                      'ทดสอบแบบทำความสะอาดและฆ่าเชื้อในขั้นตอนเดียว (one-step cleaner)',
                                      'ทดสอบแบบทำความสะอาดและฆ่าเชื้อในขั้นตอนเดียว (one-step cleaner)')],
                                  validators=[Optional()])
    sheet_organism_fields = FieldList(FormField(BacteriaSheetTestConditionForm),
                                      min_entries=len(bacteria_liquid_organisms))


class BacteriaAfterWashTestConditionForm(FlaskForm):
    after_wash_organism = CheckboxField('เชื้อ', validators=[Optional()])
    after_wash_ratio = IntegerField('อัตราส่วนเจือจางผลิตภัณฑ์', validators=[Optional()], render_kw={'class': 'input'})
    after_wash_per_water = IntegerField('ต่อน้ำ', validators=[Optional()], render_kw={'class': 'input'})
    after_wash_time_duration = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับผ้า (นาที)', validators=[Optional()],
                                            render_kw={'class': 'input'})


class BacteriaAfterWashConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์',
                               default='ผลิตภัณฑ์ฆ่าเชื้อที่ใช้ในกระบวนการซักผ้า-ผลิตภัณฑ์ที่อ้างสรรพคุณฤทธิ์ตกค้างหลังซัก (After Wash Claim)',
                               render_kw={'class': 'input is-danger'})
    after_wash_qualitative_test = RadioField('วิธีทดสอบเชิงคุณภาพ',
                                             choices=[('วิธีทดสอบเชิงคุณภาพ AOAC 962.04', 'AOAC 962.04'),
                                                      ('วิธีทดสอบเชิงคุณภาพ JIS L 1902', 'JIS L 1902'),
                                                      ('วิธีทดสอบเชิงคุณภาพ AATCC 147-2004', 'AATCC 147-2004')],
                                             validators=[Optional()])
    after_wash_quantitative_test = RadioField('วิธีทดสอบเชิงปริมาณ',
                                              choices=[('วิธีทดสอบเชิงปริมาณ JIS L 1902', 'JIS L 1902'),
                                                       ('วิธีทดสอบเชิงปริมาณ ISO 20743', 'ISO 20743'),
                                                       ('วิธีทดสอบเชิงปริมาณ AATCC 100-2004', 'AATCC 100-2004')],
                                              validators=[Optional()])
    after_wash_dilution = RadioField('การเจือจาง', choices=[('เจือจาง', 'เจือจาง'), ('ไม่เจือจาง', 'ไม่เจือจาง')],
                                     validators=[Optional()])
    after_wash_organism_fields = FieldList(FormField(BacteriaAfterWashTestConditionForm),
                                           min_entries=len(bacteria_wash_organisms))


class BacteriaInWashTestConditionForm(FlaskForm):
    in_wash_organism = CheckboxField('เชื้อ', validators=[Optional()])
    in_wash_ratio = IntegerField('อัตราส่วนเจือจางผลิตภัณฑ์', validators=[Optional()], render_kw={'class': 'input'})
    in_wash_per_water = IntegerField('ต่อน้ำ', validators=[Optional()], render_kw={'class': 'input'})
    in_wash_time_duration = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับผ้า (นาที)', validators=[Optional()],
                                         render_kw={'class': 'input'})


class BacteriaInWashConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์',
                               default='ผลิตภัณฑ์ฆ่าเชื้อที่ใช้ในกระบวนการซักผ้า-ผลิตภัณฑ์ที่อ้างสรรพคุณฤทธิ์ฆ่าเชื้อขณะซัก (In Wash Claim)',
                               render_kw={'class': 'input is-danger'})
    in_wash_test_method = RadioField('วิธีทดสอบเชิงปริมาณ',
                                     choices=[('วิธีทดสอบเชิงปริมาณ ASTM E 2274-09', 'ASTM E 2274-09')],
                                     validators=[Optional()])
    in_wash_dilution = RadioField('การเจือจาง', choices=[('เจือจาง', 'เจือจาง'), ('ไม่เจือจาง', 'ไม่เจือจาง')],
                                  validators=[Optional()])
    in_wash_organism_fields = FieldList(FormField(BacteriaInWashTestConditionForm),
                                        min_entries=len(bacteria_wash_organisms))


class BacteriaRequestForm(FlaskForm):
    sample_name = StringField('ชื่อผลิตภัณฑ์', validators=[DataRequired()],
                              render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกชื่อผลิตภัณฑ์')",
                                         "oninput": "this.setCustomValidity('')"})
    active_substance = TextAreaField('สารสำคัญที่ออกฤทธ์ และปริมาณสารสำคัญ', validators=[DataRequired()],
                                     render_kw={
                                         "oninvalid": "this.setCustomValidity('กรุณากรอกสารสำคัญที่ออกฤทธ์ และปริมาณสารสำคัญ')",
                                         "oninput": "this.setCustomValidity('')"
                                     })
    product_appearance = StringField('ลักษณะทางกายภาพของผลิตภัณฑ์', validators=[DataRequired()],
                                     render_kw={
                                         "oninvalid": "this.setCustomValidity('กรุณากรอกลักษณะทางกายภาพของผลิตภัณฑ์')",
                                         "oninput": "this.setCustomValidity('')"
                                         })
    kind = StringField('ลักษณะบรรจุภัณฑ์', validators=[DataRequired()],
                       render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกลักษณะบรรจุภัณฑ์')",
                                  "oninput": "this.setCustomValidity('')"
                                  })
    size = StringField('ขนาดบรรจุภัณฑ์', validators=[DataRequired()],
                       render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกขนาดบรรจุภัณฑ์')",
                                  "oninput": "this.setCustomValidity('')"
                                  })
    mfg = StringField('วันที่ผลิต', validators=[DataRequired()],
                      render_kw={"oninvalid": "this.setCustomValidity('กรุณาเลือกวันที่ผลิต')",
                                 "oninput": "this.setCustomValidity('')"
                                 })
    exp = StringField('วันหมดอายุ', validators=[DataRequired()],
                      render_kw={"oninvalid": "this.setCustomValidity('กรุณาเลือกวันหมดอายุ')",
                                 "oninput": "this.setCustomValidity('')"
                                 })
    lot_no = StringField('เลขที่ผลิต', validators=[DataRequired()],
                         render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกเลขที่ผลิต')",
                                    "oninput": "this.setCustomValidity('')"
                                    })
    manufacturer = StringField('ผู้ผลิต', validators=[DataRequired()],
                               render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกผู้ผลิต')",
                                          "oninput": "this.setCustomValidity('')"
                                          })
    manufacturer_address = TextAreaField('ที่อยู่ผู้ผลิต', validators=[DataRequired()],
                                         render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกที่อยู่ผู้ผลิต')",
                                                    "oninput": "this.setCustomValidity('')"
                                                    })
    importanddistributor = StringField('ผู้นำเข้า/จัดจำหน่าย', validators=[DataRequired()],
                                       render_kw={
                                           "oninvalid": "this.setCustomValidity('กรุณากรอกผู้นำเข้า/จัดจำหน่าย')",
                                           "oninput": "this.setCustomValidity('')"
                                           })
    importanddistributor_address = TextAreaField('ที่อยู่ผู้นำเข้า/จัดจำหน่าย', validators=[DataRequired()],
                                                 render_kw={
                                                     "oninvalid": "this.setCustomValidity('กรุณากรอกที่อยู่ผู้นำเข้า/จัดจำหน่าย')",
                                                     "oninput": "this.setCustomValidity('')"
                                                     })
    amount = IntegerField('จำนวนที่ส่ง', validators=[DataRequired()],
                          render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกจำนวนที่ส่ง')",
                                     "oninput": "this.setCustomValidity('')"
                                     })
    collect_sample_during_testing = SelectField('การเก็บตัวอย่างระหว่างรอทดสอบ',
                                                choices=[('', 'กรุณาเลือกการเก็บตัวอย่างระหว่างรอทดสอบ'),
                                                         ('อุณหภูมิห้อง', 'อุณหภูมิห้อง'),
                                                         ('อื่นๆ โปรดระบุ', 'อื่นๆ โปรดระบุ')],
                                                validators=[DataRequired()],
                                                render_kw={
                                                    "oninvalid": "this.setCustomValidity('กรุณาเลือกการเก็บตัวอย่างระหว่างรอทดสอบ')",
                                                    "oninput": "this.setCustomValidity('')"
                                                    })
    collect_sample_during_testing_other = StringField('ระบุ')
    product_type = SelectField('ประเภทผลิตภัณฑ์', choices=[('', '+ เพิ่มประเภทผลิตภัณฑ์'),
                                                           ('liquid',
                                                            'ผลิตภัณฑ์ฆ่าเชื้อบนพื้นผิวไม่มีรูพรุนชนิดของเหลว หรือชนิดผง ที่ละลายน้้าได้'),
                                                           ('spray',
                                                            'ผลิตภัณฑ์ฆ่าเชื้อบนพื้นผิวไม่มีรูพรุนชนิดฉีดพ่นธรรมดา หรือ ฉีดพ่นอัดก๊าซ'),
                                                           ('sheet', 'ผลิตภัณฑ์ฆ่าเชื้อชนิดแผ่น'),
                                                           ('after_wash',
                                                            'ผลิตภัณฑ์ฆ่าเชื้อที่ใช้ในกระบวนการซักผ้า-ผลิตภัณฑ์ที่อ้างสรรพคุณฤทธิ์ตกค้างหลังซัก (After Wash Claim)'),
                                                           ('in_wash',
                                                            'ผลิตภัณฑ์ฆ่าเชื้อที่ใช้ในกระบวนการซักผ้า-ผลิตภัณฑ์ที่อ้างสรรพคุณฤทธิ์ฆ่าเชื้อขณะซัก (In Wash Claim)')])
    liquid_condition_field = FormField(BacteriaLiquidConditionForm,
                                       'ผลิตภัณฑ์ฆ่าเชื้อบนพื้นผิวไม่มีรูพรุนชนิดของเหลว หรือชนิดผง ที่ละลายน้้าได้')
    spray_condition_field = FormField(BacteriaSprayConditionForm,
                                      'ผลิตภัณฑ์ฆ่าเชื้อบนพื้นผิวไม่มีรูพรุนชนิดฉีดพ่นธรรมดา หรือ ฉีดพ่นอัดก๊าซ')
    sheet_condition_field = FormField(BacteriaSheetConditionForm, 'ผลิตภัณฑ์ฆ่าเชื้อชนิดแผ่น')
    after_wash_condition_field = FormField(BacteriaAfterWashConditionForm,
                                           'ผลิตภัณฑ์ฆ่าเชื้อที่ใช้ในกระบวนการซักผ้า-ผลิตภัณฑ์ที่อ้างสรรพคุณฤทธิ์ตกค้างหลังซัก (After Wash Claim)')
    in_wash_condition_field = FormField(BacteriaInWashConditionForm,
                                        'ผลิตภัณฑ์ฆ่าเชื้อที่ใช้ในกระบวนการซักผ้า-ผลิตภัณฑ์ที่อ้างสรรพคุณฤทธิ์ฆ่าเชื้อขณะซัก (In Wash Claim)')


virus_liquid_organisms = [
    'Influenza virus A (H1N1)',
    'Enterovirus A-71',
    'Respiratory syncytial virus',
    'SARS-CoV-2'
]

virus_airborne_organisms = [
    'Influenza virus A (H1N1)'
]


class VirusLiquidTestConditionForm(FlaskForm):
    liquid_organism = CheckboxField('เชื้อ', validators=[Optional()])
    liquid_ratio = IntegerField('อัตราส่วนเจือจางผลิตภัณฑ์', validators=[Optional()], render_kw={'class': 'input'})
    liquid_per_water = IntegerField('ต่อน้ำ', validators=[Optional()], render_kw={'class': 'input'})
    liquid_time_duration_ = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับเชื้อ (วินาที/นาที)', validators=[Optional()],
                                         render_kw={'class': 'input'})


class VirusLiquidConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์',
                               default='ผลิตภัณฑ์ฆ่าเชื้อ ชนิดของเหลว ชนิดผง หรือชนิดเม็ดที่ละลายน้ำได้',
                               render_kw={'class': 'input is-danger'})
    liquid_test_method = CheckboxField('วิธีทดสอบ',
                                       choices=[(c, c) for c in ['วิธีทดสอบ ASTM E1052-20 (Virus suspension test',
                                                                 'วิธีทดสอบ ASTM E1053-20 (Nonporous environmental surfaces)',
                                                                 'วิธีทดสอบ Modified ASTM E1053-20']],
                                       validators=[Optional()])
    liquid_surface_type = RadioField('ชนิดพื้นผิว', choices=[('สิ่งทอ', 'สิ่งทอ'),
                                                             ('พื้นผิวอื่นๆ โปรดระบุ', 'พื้นผิวอื่นๆ โปรดระบุ')],
                                     validators=[Optional()])
    liquid_surface_type_other = StringField('ระบุ', render_kw={'class': 'input'})
    liquid_product_preparation = RadioField('การเตรียมผลิตภัณฑ์เพื่อการทดสอบ',
                                            choices=[('น้ำยาอยู่ในสภาพพร้อมใช้ (ready to use)',
                                                      'น้ำยาอยู่ในสภาพพร้อมใช้ (ready to use)'),
                                                     ('ต้องมีการเจือจางหรือละลายด้วยน้ำก่อนใช้งาน',
                                                      'ต้องมีการเจือจางหรือละลายด้วยน้ำก่อนใช้งาน')],
                                            validators=[Optional()])
    liquid_organism_fields = FieldList(FormField(VirusLiquidTestConditionForm), min_entries=len(virus_liquid_organisms))


class VirusSprayTestConditionForm(FlaskForm):
    spray_organism = CheckboxField('เชื้อ', validators=[Optional()])
    spray_ratio = IntegerField('อัตราส่วนเจือจางผลิตภัณฑ์', validators=[Optional()], render_kw={'class': 'input'})
    spray_per_water = IntegerField('ต่อน้ำ', validators=[Optional()], render_kw={'class': 'input'})
    spray_distance = IntegerField('ระยะห่างในการฉีดพ่น (cm)', validators=[Optional()], render_kw={'class': 'input'})
    spray_of_time = IntegerField('ระยะเวลาฉีดพ่น (วินาที)', validators=[Optional()], render_kw={'class': 'input'})
    spray_time_duration = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับเชื้อ (วินาที/นาที)', validators=[Optional()],
                                       render_kw={'class': 'input'})


class VirusSprayConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์',
                               default='ผลิตภัณฑ์ฆ่าเชื้อ ชนิดฉีดพ่น',
                               render_kw={'class': 'input is-danger'})
    spray_inject_type = RadioField('ประเภทการฉีด',
                                   choices=[('ฉีดพ่นธรรมดา (Trigger spray)', 'ฉีดพ่นธรรมดา (Trigger spray)'),
                                            ('ฉีดพ่นอัดก๊าซ (Aerosol spray)', 'ฉีดพ่นอัดก๊าซ (Aerosol spray)')],
                                   validators=[Optional()])
    spray_test_method = CheckboxField('วิธีทดสอบ', choices=[(c, c) for c in [
        'วิธีทดสอบ ASTM E1053-20 (Nonporous environmental surfaces)',
        'วิธีทดสอบ Modified ASTM E1053-20']],
                                      validators=[Optional()])

    spray_surface_type = RadioField('ชนิดพื้นผิว', choices=[('สิ่งทอ', 'สิ่งทอ'),
                                                            ('พื้นผิวอื่นๆ โปรดระบุ', 'พื้นผิวอื่นๆ โปรดระบุ')],
                                    validators=[Optional()])
    spray_surface_type_other = StringField('ระบุ', render_kw={'class': 'input'})
    spray_product_preparation = RadioField('การเตรียมผลิตภัณฑ์เพื่อการทดสอบ',
                                           choices=[('น้ำยาอยู่ในสภาพพร้อมใช้ (ready to use)',
                                                     'น้ำยาอยู่ในสภาพพร้อมใช้ (ready to use)'),
                                                    ('ต้องมีการเจือจางหรือละลายด้วยน้ำก่อนใช้งาน (แนบขวดสเปรย์มาด้วย)',
                                                     'ต้องมีการเจือจางหรือละลายด้วยน้ำก่อนใช้งาน (แนบขวดสเปรย์มาด้วย)')],
                                           validators=[Optional()])
    spray_organism_fields = FieldList(FormField(VirusSprayTestConditionForm), min_entries=len(virus_liquid_organisms))


class VirusCoatTestConditionForm(FlaskForm):
    coat_organism = CheckboxField('เชื้อ', validators=[Optional()])
    coat_time_duration = IntegerField('ระยะเวลาที่ผลิตภัณฑ์สัมผัสกับเชื้อ (วินาที/นาที)', validators=[Optional()],
                                      render_kw={'class': 'input'})


class VirusCoatConditionForm(FlaskForm):
    product_type = HiddenField('ประเภทผลิตภัณฑ์', default='ผลิตภัณฑ์ฆ่าเชื้อที่เคลือบบนพื้นผิวสำเร็จรูป',
                               render_kw={'class': 'input is-danger'})
    coat_test_method = CheckboxField('วิธีทดสอบ', choices=[(c, c) for c in ['วิธีทดสอบ Modified ASTM E1053-20']],
                                     validators=[Optional()])
    coat_specify_surface_type = StringField('ระบุชนิดของพื้นผิว', render_kw={'class': 'input'})
    coat_organism_fields = FieldList(FormField(VirusCoatTestConditionForm), min_entries=len(virus_liquid_organisms))


class VirusDisinfectionRequestForm(FlaskForm):
    product_name = StringField('ชื่อผลิตภัณฑ์', validators=[DataRequired()],
                               render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกชื่อผลิตภัณฑ์')",
                                          "oninput": "this.setCustomValidity('')"
                                          })
    active_substance = TextAreaField('สารสำคัญที่ออกฤทธ์ และปริมาณสารสำคัญ', validators=[DataRequired()],
                                     render_kw={
                                         "oninvalid": "this.setCustomValidity('กรุณากรอกสารสำคัญที่ออกฤทธิ์ และปริมาณสารสำคัญ')",
                                         "oninput": "this.setCustomValidity('')"
                                         })
    product_appearance = StringField('ลักษณะทางกายภาพของผลิตภัณฑ์', validators=[DataRequired()],
                                     render_kw={
                                         "oninvalid": "this.setCustomValidity('กรุณากรอกลักษณะทางกายภาพของผลิตภัณฑ์')",
                                         "oninput": "this.setCustomValidity('')"
                                         })
    kind = StringField('ลักษณะบรรจุภัณฑ์', validators=[DataRequired()],
                       render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกลักษณธบรรจุภัณฑ์')",
                                  "oninput": "this.setCustomValidity('')"
                                  })
    size = StringField('ขนาดบรรจุภัณฑ์', validators=[DataRequired()],
                       render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกขนาดบรรจุภัณฑ์')",
                                  "oninput": "this.setCustomValidity('')"
                                  })
    mfg = StringField('วันที่ผลิต', validators=[DataRequired()],
                      render_kw={"oninvalid": "this.setCustomValidity('กรุณาเลือกวันที่ผลิต')",
                                 "oninput": "this.setCustomValidity('')"
                                 })
    exp = StringField('วันหมดอายุ', validators=[DataRequired()],
                      render_kw={"oninvalid": "this.setCustomValidity('กรุณาเลือกวันหมดอายุ')",
                                 "oninput": "this.setCustomValidity('')"
                                 })
    lot_no = StringField('เลขที่ผลิต', validators=[DataRequired()],
                         render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกเลขที่ผลิต')",
                                    "oninput": "this.setCustomValidity('')"
                                    })
    amount = IntegerField('จำนวนที่ส่ง', validators=[DataRequired()],
                          render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกจำนวนที่ส่ง')",
                                     "oninput": "this.setCustomValidity('')"
                                     })
    service_life = StringField('อายุการใช้งานหลังการเปิดใช้', validators=[DataRequired()],
                               render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกอายุการใช้งานหลังดารเปิดใช้')",
                                          "oninput": "this.setCustomValidity('')"
                                          })
    product_storage = SelectField('การเก็บรักษาผลิตภัณฑ์',
                                  choices=[('', 'กรุณาเลือกการเก็บรักษาผลิตภัณฑ์'),
                                           ('เก็บรักษาที่อุณหภูมิห้อง', 'เก็บรักษาที่อุณหภูมิห้อง'),
                                           ('อื่นๆ โปรดระบุ', 'อื่นๆ โปรดระบุ')], validators=[DataRequired()],
                                  render_kw={"oninvalid": "this.setCustomValidity('กรุณาเลือกการเก็บรักษาผลิตภัณฑ์')",
                                             "oninput": "this.setCustomValidity('')"
                                             })
    product_storage_other = StringField('ระบุ')
    product_type = SelectField('ประเภทผลิตภัณฑ์', choices=[('', '+ เพิ่มประเภทผลิตภัณฑ์'),
                                                           ('liquid',
                                                            'ผลิตภัณฑ์ฆ่าเชื้อชนิดของเหลว ชนิดผง หรือชนิดเม็ดที่ละลายน้ำได้'),
                                                           ('spray', 'ผลิตภัณฑ์ฆ่าเชื้อชนิดฉีดพ่น'),
                                                           ('coat', 'ผลิตภัณฑ์ฆ่าเชื้อที่เคลือบบนพื้นผิวสำเร็จรูป')],
                               validators=[Optional()])
    liquid_condition_field = FormField(VirusLiquidConditionForm,
                                       'ผลิตภัณฑ์ฆ่าเชื้อชนิดของเหลว ชนิดผง หรือชนิดเม็ดที่ละลายน้ำได้')
    spray_condition_field = FormField(VirusSprayConditionForm, 'ผลิตภัณฑ์ฆ่าเชื้อชนิดฉีดพ่น')
    coat_condition_field = FormField(VirusCoatConditionForm, 'ผลิตภัณฑ์ฆ่าเชื้อที่เคลือบบนพื้นผิวสำเร็จรูป')


class VirusSurfaceDisinfectionTestConditionForm(FlaskForm):
    surface_disinfection_organism = CheckboxField('เชื้อ', validators=[Optional()])
    surface_disinfection_period_test = StringField('ระยะเวลาที่ต้องการทดสอบเพื่อทำลายเชื้อ (วินาที/นาที)',
                                                   validators=[Optional()],
                                                   render_kw={'class': 'input',
                                                              'placeholder': 'เช่น  1 วินาที หรือ 1 นาที'})


class VirusSurfaceDisinfectionConditionForm(FlaskForm):
    product_type = HiddenField('รายการทดสอบ',
                               default='การฆ่าเชื้อบนพื้นผิว',
                               render_kw={'class': 'input is-danger'})
    surface_disinfection_clean_type = RadioField(
        'รูปแบบการทดสอบ',
        choices=[
            ('ทดสอบการฆ่าเชื้อบนพื้นผิวเรียบไม่มีรูพรุน (มาตรฐานวิธีทดสอบ ASTM E1053-20 ใช้พื้นผิววัสดุแก้ว)',
             'ทดสอบการฆ่าเชื้อบนพื้นผิวเรียบไม่มีรูพรุน (มาตรฐานวิธีทดสอบ ASTM E1053-20 ใช้พื้นผิววัสดุแก้ว)'),
            ('ทดสอบการฆ่าเชื้อบนพื้นผิวชนิดอื่นๆ โปรดระบุ', 'ทดสอบการฆ่าเชื้อบนพื้นผิวชนิดอื่นๆ โปรดระบุ')
        ], validators=[Optional()])
    surface_disinfection_clean_type_other = StringField('ระบุ', render_kw={'class': 'input'})
    surface_disinfection_organism_fields = FieldList(FormField(VirusSurfaceDisinfectionTestConditionForm),
                                                     min_entries=len(virus_liquid_organisms))


class VirusAirborneDisinfectionTestConditionForm(FlaskForm):
    airborne_disinfection_organism = CheckboxField('เชื้อ', validators=[Optional()])
    airborne_disinfection_period_test = StringField('ระยะเวลาที่ต้องการทดสอบเพื่อทำลายเชื้อ (วินาที/นาที)',
                                                    validators=[Optional()],
                                                    render_kw={'class': 'input',
                                                               'placeholder': 'เช่น  1 วินาที หรือ 1 นาที'})


class VirusAirborneDisinfectionConditionForm(FlaskForm):
    product_type = HiddenField('รายการทดสอบ',
                               default='การลด/ทำลายเชื้อในอากาศ',
                               render_kw={'class': 'input is-danger'})
    airborne_disinfection_clean_type = RadioField(
        'รูปแบบการทดสอบ',
        choices=[
            ('ทดสอบการลดปริมาณเชื้อในอากาศ (เครื่องฟอกอากาศ)', 'ทดสอบการลดปริมาณเชื้อในอากาศ (เครื่องฟอกอากาศ)'),
            ('ทดสอบการทำลายเชื้อในอากาศ (เครื่องปล่อยสารหรืออนุภาคทำลายเชื้อ)',
             'ทดสอบการทำลายเชื้อในอากาศ (เครื่องปล่อยสารหรืออนุภาคทำลายเชื้อ)')
        ], validators=[Optional()])
    airborne_disinfection_organism_fields = FieldList(FormField(VirusAirborneDisinfectionTestConditionForm),
                                                      min_entries=len(virus_airborne_organisms))


class VirusAirDisinfectionRequestForm(FlaskForm):
    product_name = StringField('ชื่อผลิตภัณฑ์', validators=[DataRequired()],
                               render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกชื่อผลิตภัณฑ์')",
                                          "oninput": "this.setCustomValidity('')"
                                          })
    disinfection_system = TextAreaField('ระบบการกำจัดเชื้อของผลิตภัณฑ์', validators=[DataRequired()],
                                        render_kw={
                                            "oninvalid": "this.setCustomValidity('กรุณากรอกระบบการกำจัดเชื้อของผลิตภัณฑ์')",
                                            "oninput": "this.setCustomValidity('')"
                                            })
    model = StringField('รุ่น', validators=[DataRequired()],
                        render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกรุ่น')",
                                   "oninput": "this.setCustomValidity('')"
                                   })
    serial_no = StringField('หมายเลขประจำเครื่อง', validators=[DataRequired()],
                            render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกหมายเลขประจำเครื่อง')",
                                       "oninput": "this.setCustomValidity('')"
                                       })
    equipment_test_operation = TextAreaField('วิธีการใช้งานเครื่องหรืออุปกรณ์เพื่อทำการทดสอบ',
                                             validators=[DataRequired()],
                                             render_kw={
                                                 "oninvalid": "this.setCustomValidity('กรุณากรอกวิธีใช้งานเครื่องหรืออุปกรณ์เพื่อทำการทดสอบ')",
                                                 "oninput": "this.setCustomValidity('')"
                                                 })
    manufacturer = StringField('ผู้ผลิต', validators=[DataRequired()],
                               render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกชื่อผู้ผลิต')",
                                          "oninput": "this.setCustomValidity('')"
                                          })
    manufacturer_address = TextAreaField('ที่อยู่ผู้ผลิต', validators=[DataRequired()],
                                         render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกที่อยู่ผู้ผลิต')",
                                                    "oninput": "this.setCustomValidity('')"
                                                    })
    importer = StringField('ผู้นำเข้า', validators=[DataRequired()],
                           render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกชื่อผู้นำเข้า')",
                                      "oninput": "this.setCustomValidity('')"
                                      })
    importer_address = TextAreaField('ที่อยู่ผู้นำเข้า', validators=[DataRequired()],
                                     render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกที่อยู่ผู้นำเข้า')",
                                                "oninput": "this.setCustomValidity('')"
                                                })
    distributor = StringField('ผู้จัดจำหน่าย', validators=[DataRequired()],
                              render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกชื่อผู้จัดจำหน่าย')",
                                         "oninput": "this.setCustomValidity('')"
                                         })
    distributor_address = TextAreaField('ที่อยู่ผู้จัดจำหน่าย', validators=[DataRequired()],
                                        render_kw={
                                            "oninvalid": "this.setCustomValidity('กรุณากรอกที่อยู่ผู้จัดจำหน่าย')",
                                            "oninput": "this.setCustomValidity('')"
                                            })
    product_type = SelectField('ประเภทการฆ่า/ทำลายเชื้อ', choices=[('', '+ เพิ่มประเภทการฆ่า/ทำลายเชื้อ'),
                                                                   ('surface', 'การฆ่าเชื้อบนพื้นผิว'),
                                                                   ('airborne', 'การลด/ทำลายเชื้อในอากาศ')],
                               validators=[Optional()])
    surface_condition_field = FormField(VirusSurfaceDisinfectionConditionForm, 'การฆ่าเชื้อบนพื้นผิว')
    airborne_condition_field = FormField(VirusAirborneDisinfectionConditionForm, 'การลด/ทำลายเชื้อในอากาศ')


class HeavyMetalConditionForm(FlaskForm):
    no = IntegerField('ลำดับ', validators=[DataRequired()],
                                     render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกลำดับ')",
                                                "oninput": "this.setCustomValidity('')"
                                                })
    sample_name = StringField('ตัวอย่าง', validators=[DataRequired()],
                                     render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกตัวอย่าง')",
                                                "oninput": "this.setCustomValidity('')"
                                                })
    quantity = StringField('ปริมาณ',  validators=[DataRequired()],
                                     render_kw={"oninvalid": "this.setCustomValidity('กรุณาปริมาณ')",
                                                "oninput": "this.setCustomValidity('')"
                                                })
    parameter_test = CheckboxField('สารทดสอบ', choices=[('ตะกั่ว/Lead', 'ตะกั่ว/Lead'),
                                    ('ทองแดง/Copper', 'ทองแดง/Copper'),
                                    ('สารหนู/Arsenic', 'สารหนู/Arsenic'),
                                    ('สังกะสี/Zinc', 'สังกะสี/Zinc'),
                                    ('ปรอท/Mercury', 'ปรอท/Mercury'),
                                    ('แคดเมียม/Cadmium', 'แคดเมียม/Cadmium'),
                                    ('อื่นๆ/Other', 'อื่นๆ/Other')], validators=[DataRequired()])
    parameter_test_other = StringField('ระบุ')


class HeavyMetalRequestForm(FlaskForm):
    objective = RadioField('วัตถุประสงค์',
                           choices=[('เพื่อทราบผล/General info.', 'เพื่อทราบผล/General info.'),
                                    ('จำหน่ำยในประเทศ/Domestic', 'จำหน่ำยในประเทศ/Domestic'),
                                    ('ยื่นขอ อย./Thai FDA', 'ยื่นขอ อย./Thai FDA'),
                                    ('ส่งออก/Export', 'ส่งออก/Export'),
                                    ('งานวิจัย/Reserch', 'งานวิจัย/Reserch'),
                                    ('อื่นๆ/Other', 'อื่นๆ/Other')], validators=[DataRequired()])
    objective_other = StringField('ระบุ')
    temp_at_received = RadioField('อุณหภูมิขณะรับตัวอย่าง',
                                  choices=[('อุณหภูมิห้อง/Room temp.', 'อุณหภูมิห้อง/Room temp.'),
                                           ('แช่แข็ง/Frozen', 'แช่แข็ง/Frozen'),
                                           ('แช่เย็น/Chilled', 'แช่เย็น/Chilled')],
                                  validators=[DataRequired()])
    standard_limitation = RadioField('ระบุค่ามาตรฐาน', choices=[('EU', 'EU'),
                                                                ('CODEX', 'CODEX'),
                                                                ('Japan', 'Japan'),
                                                                ('ACFS', 'ACFS'),
                                                                ('Other', 'Other')],
                                     validators=[DataRequired()])
    standard_limitation_other = StringField('ระบุ')
    duration_of_report = RadioField('ระยะเวลาในการรายงานผล',
                                    choices=[('ปกติ/Regular (7 วันทำการ)', 'ปกติ/Regular (7 วันทำการ)'),
                                             ('ด่วนพิเศษ/Fast track (3 วันทำการ)',
                                              'ด่วนพิเศษ/Fast track (3 วันทำการ คิดค่าบริการ 500 ฿)')],
                                    validators=[DataRequired()])
    other_service = RadioField('บริการอื่นๆ', choices=[
        ('ค่าความไม่แน่นอน/Uncertainty', 'ค่าความไม่แน่นอน/Uncertainty (คิดค่าบริการ 200฿/สำร)'),
        ('Other', 'Other (มีค่าบริการเพิ่มเติม)')])
    other_service_note = StringField('ระบุ')
    heavy_metal_condition_field = FieldList(FormField(HeavyMetalConditionForm), min_entries=1)


class ServiceQuotationForm(ModelForm):
    class Meta:
        model = ServiceQuotation
        exclude = ['digital_signature']

    reason = RadioField('เหตุผล', choices=[(c, c) for c in
                                           ['โครงการเลื่อน/ยกเลิก', 'ราคาไม่ตรงงบประมาณ', 'บริการไม่ตรงความต้องการ',
                                            'ข้อมูลในใบเสนอราคาไม่ครบถ้วน / ไม่ถูกต้อง', 'อื่นๆ']],
                        validators=[Optional()])


class ServiceSampleForm(ModelForm):
    class Meta:
        model = ServiceSample

    ship_type = RadioField('วิธีการส่งตัวอย่าง', choices=[(c, c) for c in ['ส่งด้วยตนเอง', 'ส่งทางไปรษณีย์']],
                           validators=[DataRequired()])


class ServicePaymentForm(ModelForm):
    class Meta:
        model = ServicePayment

    file_upload = FileField('File Upload')


class ServiceResultItemForm(ModelForm):
    class Meta:
        model = ServiceResultItem
