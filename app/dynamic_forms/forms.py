from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, IntegerField
from wtforms.validators import InputRequired, Optional, NumberRange
from wtforms_alchemy import QuerySelectField
from .models import DynamicFormVersion


class DynamicFormCreateForm(FlaskForm):
    name = StringField('Form name', description='ตั้งชื่อแบบฟอร์มให้ชัดเจน เพื่อให้อาจารย์และผู้ใช้งานเข้าใจได้ทันที', render_kw={'placeholder': 'เช่น แบบประเมินโครงงานปลายภาค'}, validators=[InputRequired()])
    description = TextAreaField('Description', description='อธิบายวัตถุประสงค์ของแบบฟอร์มและช่วงเวลาหรือกรณีที่ควรใช้งาน', render_kw={'placeholder': 'เช่น ใช้ประเมินทักษะการนำเสนอและการแก้ปัญหาจากโครงงาน'}, validators=[Optional()])
    status = SelectField('Status', choices=[('Draft', 'Draft'), ('Published', 'Published'), ('Archived', 'Archived')], validators=[InputRequired()])


class DynamicFormFieldForm(FlaskForm):
    key = StringField('Field key', description='รหัสภายในสำหรับจัดเก็บคำตอบ ใช้อักษรภาษาอังกฤษตัวพิมพ์เล็ก ตัวเลข และขีดล่าง เช่น communication_score', render_kw={'placeholder': 'เช่น communication_score'}, validators=[InputRequired()])
    label = StringField('Label', description='ข้อความที่จะแสดงให้ผู้กรอกแบบฟอร์มเห็น', render_kw={'placeholder': 'เช่น ทักษะการสื่อสาร'}, validators=[InputRequired()])
    field_type = SelectField('Field type', description='เลือกรูปแบบที่ผู้ใช้งานจะใช้กรอกหรือเลือกคำตอบ', choices=[
        ('text', 'Text'), ('textarea', 'Long text'), ('number', 'Number'),
        ('rating', 'Rating'), ('boolean', 'Yes/No'), ('date', 'Date'),
        ('select', 'Select'), ('multiselect', 'Multiple selection'),
    ], validators=[InputRequired()])
    required = BooleanField('Required', description='กำหนดให้ผู้ใช้งานต้องตอบคำถามนี้ก่อนส่งแบบฟอร์ม')
    display_order = IntegerField('Display order', description='ลำดับการแสดงผลในแบบฟอร์ม ตัวเลขน้อยจะแสดงก่อน', validators=[InputRequired(), NumberRange(min=1)], default=1)
    help_text = TextAreaField('Help text', description='คำแนะนำเพิ่มเติมที่จะแสดงใต้ช่องกรอก เพื่อช่วยให้ผู้ใช้งานตอบได้ถูกต้อง', render_kw={'placeholder': 'เช่น ให้คะแนนจากผลงานที่นักศึกษานำเสนอ'}, validators=[Optional()])
    options = TextAreaField('Options', description='ใช้กับ Select หรือ Multiple selection โดยใส่หนึ่งตัวเลือกต่อหนึ่งบรรทัดในรูปแบบ value|label เช่น 1|ดีมาก', render_kw={'placeholder': '1|ต้องปรับปรุง\n2|พอใช้\n3|ดี\n4|ดีมาก'}, validators=[Optional()])


def create_assignment_form():
    class DynamicFormAssignmentForm(FlaskForm):
        version = QuerySelectField(
            'Evaluation form',
            description='เลือกเวอร์ชันของแบบประเมินที่จะผูกกับหลักฐานนี้',
            query_factory=lambda: DynamicFormVersion.query.order_by(
                DynamicFormVersion.form_id.asc(), DynamicFormVersion.version.desc()).all(),
            get_label=lambda version: '{} · v{} ({})'.format(
                version.form.name, version.version, version.status),
            allow_blank=False,
            validators=[InputRequired()],
        )
    return DynamicFormAssignmentForm
