# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, TextAreaField, FileField, SelectField
from wtforms.validators import DataRequired
from app.models import Org

class RegisterAccountForm(FlaskForm):
    title = StringField(u'เรื่อง')
    number = StringField(u'เลขหนังสือ')
    section = StringField(u'หัวข้อการจัดซื้อ')
    description = TextAreaField(u'คำอธิบาย')
    creation_date = DateTimeField(u';วันที่สร้าง Account', validators=[DataRequired()])
    upload_file = FileField(u'อัพโหลดไฟล์')



class DeliveryForm(FlaskForm):
    previous_location = SelectField(u'สถานที่ก่อนหน้า',
                                    choices=[('salaya', u'ศาลายา'),
                                             ('siriraj', u'ศิริราช'),
                                             ('other', u'อื่นๆ')])
    next_locations = SelectField(u'สถานที่ถัดไป',
                             choices=[('salaya', u'ศาลายา'),
                                           ('siriraj', u'ศิริราช'),
                                           ('other', u'อื่นๆ')])
    no = StringField(u'เลขที่ อว')
    employee_name = StringField(u'ชื่อพนักงาน')
    desc = TextAreaField(u'รายละเอียด')
    problem_type = SelectField(u'ประเภทมีปัญหา',
                                 choices=[('incomplete', u'ข้อมูลไม่ครบ'),
                                          ('Not yet signed', u'ยังไม่ได้ลงนาม'),
                                          ('other', u'อื่นๆ')])
    note = TextAreaField(u'หมายเหตุ')
    start = DateTimeField(u'เริ่ม', validators=[DataRequired()])
    end = DateTimeField(u'สิ้นสุด', validators=[DataRequired()])
    upload = FileField(u'อัพโหลดภาพ')

