from flask_wtf import FlaskForm
from wtforms import FileField, FieldList, FormField, RadioField, widgets, PasswordField, StringField, IntegerField, \
    HiddenField, TextAreaField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Optional
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.academic_services.models import *
from flask_login import current_user
from sqlalchemy import or_

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class PasswordOfSignDigitalForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])


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


class CheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


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
    after_wash_qualitative_test = RadioField('วิธีทดสอบเชิงคุณภาพ', choices=[('AOAC 962.04', 'AOAC 962.04'),
                                                                             ('JIS L 1902', 'JIS L 1902'),
                                                                             ('AATCC 147-2004', 'AATCC 147-2004')],
                                             validators=[Optional()])
    after_wash_quantitative_test = RadioField('วิธีทดสอบเชิงปริมาณ', choices=[('JIS L 1902', 'JIS L 1902'),
                                                                              ('ISO 20743', 'ISO 20743'),
                                                                              ('AATCC 100-2004', 'AATCC 100-2004')],
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
    in_wash_test_method = RadioField('วิธีทดสอบ', choices=[('ASTM E 2274-09', 'ASTM E 2274-09')],
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
                                     render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกลักษณะทางกายภาพของผลิตภัณฑ์')",
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
                                         render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกผู้นำเข้า/จัดจำหน่าย')",
                                                    "oninput": "this.setCustomValidity('')"
                                                    })
    importanddistributor_address = TextAreaField('ที่อยู่ผู้นำเข้า/จัดจำหน่าย', validators=[DataRequired()],
                                                 render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกที่อยู่ผู้นำเข้า/จัดจำหน่าย')",
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
                                                render_kw={"oninvalid": "this.setCustomValidity('กรุณาเลือกการเก็บตัวอย่างระหว่างรอทดสอบ')",
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
                                        'ผลิตภัณฑ์ฆ่าเชื้อที่ใช้ในกระบวนการซักผ้า-ผลิตภัณฑ์ที่อ้างสรรพคุณฤทธิ์ฆ่าเชื้อขณะซัก (After Wash Claim)')


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
                                                render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกสารสำคัญที่ออกฤทธิ์ และปริมาณสารสำคัญ')",
                                                        "oninput": "this.setCustomValidity('')"
                                                    })
    product_appearance = StringField('ลักษณะทางกายภาพของผลิตภัณฑ์', validators=[DataRequired()],
                                                render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกลักษณะทางกายภาพของผลิตภัณฑ์')",
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
    surface_disinfection_period_test = IntegerField('ระยะเวลาที่ต้องการทดสอบเพื่อทำลายเชื้อ (วินาที/นาที)',
                                                    validators=[Optional()],
                                                    render_kw={'class': 'input'})


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
    airborne_disinfection_period_test = IntegerField('ระยะเวลาที่ต้องการทดสอบเพื่อทำลายเชื้อ (วินาที/นาที)',
                                                     validators=[Optional()],
                                                     render_kw={'class': 'input'})


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
                                                render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกระบบการกำจัดเชื้อของผลิตภัณฑ์')",
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
                                                render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกวิธีใช้งานเครื่องหรืออุปกรณ์เพื่อทำการทดสอบ')",
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
                                                render_kw={"oninvalid": "this.setCustomValidity('กรุณากรอกที่อยู่ผู้จัดจำหน่าย')",
                                                        "oninput": "this.setCustomValidity('')"
                                                    })
    product_type = SelectField('ประเภทการฆ่า/ทำลายเชื้อ', choices=[('', '+ เพิ่มประเภทการฆ่า/ทำลายเชื้อ'),
                                                                   ('surface', 'การฆ่าเชื้อบนพื้นผิว'),
                                                                   ('airborne', 'การลด/ทำลายเชื้อในอากาศ')],
                               validators=[Optional()])
    surface_condition_field = FormField(VirusSurfaceDisinfectionConditionForm, 'การฆ่าเชื้อบนพื้นผิว')
    airborne_condition_field = FormField(VirusAirborneDisinfectionConditionForm, 'การลด/ทำลายเชื้อในอากาศ')


def formatted_request_data():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id),
                                            ServiceRequest.lab.in_(sub_labs)))
    return query


class ServiceResultForm(ModelForm):
    class Meta:
        model = ServiceResult


def crate_address_form(use_type=False):
    class ServiceCustomerAddressForm(ModelForm):
        class Meta:
            model = ServiceCustomerAddress

        if use_type == True:
            address_type = RadioField('ประเภทที่อยู่', choices=[(c, c) for c in ['ที่อยู่จัดส่งเอกสาร',
                                                                                 'ที่อยู่ใบเสนอราคา/ใบแจ้งหนี้/ใบกำกับภาษี']],
                                      validators=[DataRequired()])
        name = StringField(validators=[DataRequired()])
        address = StringField('ที่อยู่', validators=[DataRequired()])
        province = QuerySelectField('จังหวัด', query_factory=lambda: Province.query.order_by(Province.name),
                                    allow_blank=True,
                                    blank_text='กรุณาเลือกจังหวัด', get_label='name',
                                    validators=[DataRequired(message='กรุณาเลือกจังหวัด')])
        district = QuerySelectField('เขต/อำเภอ', query_factory=lambda: [],
                                    allow_blank=True,
                                    blank_text='กรุณาเลือกเขต/อำเภอ', get_label='name',
                                    validators=[DataRequired(message='กรุณาเลือกเขต/อำเภอ')])
        subdistrict = QuerySelectField('แขวง/ตำบล',
                                       query_factory=lambda: [],
                                       allow_blank=True,
                                       blank_text='กรุณาเลือกแขวง/ตำบล', get_label='name',
                                       validators=[DataRequired(message='กรุณาเลือกแขวง/ตำบล')])
        zipcode = StringField('รหัสไปรษณีย์', validators=[DataRequired()])
        phone_number = StringField('เบอร์โทรศัพท์', validators=[DataRequired()])

    return ServiceCustomerAddressForm


def create_quotation_item_form(is_form=False):
    class ServiceQuotationItemForm(ModelForm):
        class Meta:
            model = ServiceQuotationItem
            if is_form == True:
                exclude = ['total_price']
            if is_form == False:
                exclude = ['item', 'quantity', 'unit_price', 'total_price']

    return ServiceQuotationItemForm


class ServiceQuotationForm(ModelForm):
    class Meta:
        model = ServiceQuotation
        exclude = ['digital_signature']

    quotation_items = FieldList(FormField(create_quotation_item_form(is_form=False), default=ServiceQuotationItem))


class ServiceSampleForm(ModelForm):
    class Meta:
        model = ServiceSample

    sample_integrity = RadioField('สภาพความสมบูรณ์ของตัวอย่าง', choices=[(c, c) for c in ['สมบูรณ์', 'ไม่สมบูรณ์']],
                                  default='สมบูรณ์', validators=[Optional()])
    packaging_sealed = RadioField('สภาพการปิดสนิทของภาชนะบรรจุตัวอย่าง',
                                  choices=[(c, c) for c in ['ปิดสนิท', 'ปิดไม่สนิท']],
                                  default='ปิดสนิท', validators=[Optional()])
    container_strength = RadioField('ความแข็งแรงของภาชนะบรรจุตัวอย่าง',
                                    choices=[(c, c) for c in ['แข็งแรง', 'ไม่แข็งแรง']],
                                    default='แข็งแรง', validators=[Optional()])
    container_durability = RadioField('ความคงทนของภาชนะบรรจุตัวอย่าง', choices=[(c, c) for c in ['คงทน', 'ไม่คงทน']],
                                      default='คงทน', validators=[Optional()])
    container_damage = RadioField('สภาพการแตก/หักของภาชนะบรรจุตัวอย่าง',
                                  choices=[(c, c) for c in ['ไม่แตก/หัก', 'แตก/หัก']],
                                  default='ไม่แตก/หัก', validators=[Optional()])
    info_match = RadioField('รายละเอียดบนภาชนะบรรจุตัวอย่างตรงกับใบคำขอรับบริการ',
                            choices=[(c, c) for c in ['ตรง', 'ไม่ตรง']],
                            default='ตรง', validators=[Optional()])
    same_production_lot = RadioField('ตัวอย่างชุดเดียวกันแต่มีหลายชิ้น (ถ้ามี)', choices=[(c, c) for c in [
        'ทุกชิ้นเป็นรุ่นผลิตเดียวกัน', 'มีชิ้นที่ไม่ใช่รุ่นผลิตเดียวกัน']],
                                     validators=[Optional()])


class ServiceInvoiceForm(ModelForm):
    class Meta:
        model = ServiceInvoice

    file_upload = FileField('File Upload')


class ServiceResultForm(ModelForm):
    class Meta:
        model = ServiceResult


class ServiceResultItemForm(ModelForm):
    class Meta:
        model = ServiceResultItem

    file_upload = FileField('File Upload')


class ServicePaymentForm(ModelForm):
    class Meta:
        model = ServicePayment

    file_upload = FileField('File Upload')
