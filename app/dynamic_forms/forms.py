from flask_wtf import FlaskForm
from wtforms import (StringField, TextAreaField, SelectField, BooleanField,
                     IntegerField, DecimalField)
from wtforms.validators import InputRequired, Optional, NumberRange, ValidationError
from wtforms_alchemy import QuerySelectField
from .models import DynamicFormVersion


class DynamicFormDeleteForm(FlaskForm):
    pass


class DynamicFormCreateForm(FlaskForm):
    name = StringField('Form name', description='ตั้งชื่อแบบฟอร์มให้ชัดเจน เพื่อให้อาจารย์และผู้ใช้งานเข้าใจได้ทันที', render_kw={'placeholder': 'เช่น แบบประเมินโครงงานปลายภาค'}, validators=[InputRequired()])
    description = TextAreaField('Description', description='อธิบายวัตถุประสงค์ของแบบฟอร์มและช่วงเวลาหรือกรณีที่ควรใช้งาน', render_kw={'placeholder': 'เช่น ใช้ประเมินทักษะการนำเสนอและการแก้ปัญหาจากโครงงาน'}, validators=[Optional()])
    status = SelectField('Status', choices=[('Draft', 'Draft'), ('Published', 'Published'), ('Archived', 'Archived')], validators=[InputRequired()])
    passing_percentage = DecimalField(
        'Passing percentage',
        description='เปอร์เซ็นต์คะแนนรวมขั้นต่ำที่ถือว่าผ่าน (0–100)',
        validators=[Optional(), NumberRange(min=0, max=100)],
        render_kw={'placeholder': 'เช่น 60', 'min': '0', 'max': '100',
                   'step': '0.01'},
    )


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
    scorable = BooleanField('Include in score', description='นำคำตอบของ field นี้ไปคำนวณคะแนนถ่วงน้ำหนัก')
    max_score = DecimalField('Maximum raw score', description='คะแนนดิบสูงสุด เช่น 5', validators=[Optional(), NumberRange(min=0.01)])
    weight = DecimalField('Weight multiplier', description='ตัวคูณคะแนน เช่น คะแนนดิบ 1 และน้ำหนัก 2 จะได้คะแนนถ่วงน้ำหนัก 2', validators=[Optional(), NumberRange(min=0)])

    def validate_scorable(self, field):
        if not field.data:
            return
        if self.field_type.data not in ('number', 'rating', 'select'):
            raise ValidationError('Only Number, Rating, and Select fields can be included in the score.')
        if self.max_score.data is None:
            raise ValidationError('Maximum raw score is required for a scorable field.')
        if self.weight.data is None:
            raise ValidationError('Weight is required for a scorable field.')

    def validate_options(self, field):
        if not self.scorable.data or self.field_type.data != 'select':
            return
        values = [line.partition('|')[0].strip()
                  for line in (field.data or '').splitlines() if line.strip()]
        if not values:
            raise ValidationError('A scorable Select field requires numeric options.')
        try:
            [float(value) for value in values]
        except ValueError:
            raise ValidationError('Every option value must be numeric when the field is scorable.')


class DynamicFormPassingScoreForm(FlaskForm):
    passing_percentage = DecimalField(
        'Passing percentage',
        description='เปอร์เซ็นต์คะแนนรวมขั้นต่ำที่ถือว่าผ่าน (0–100)',
        validators=[Optional(), NumberRange(min=0, max=100)],
        render_kw={'placeholder': 'เช่น 60'},
    )


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
