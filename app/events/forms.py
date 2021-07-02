# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, TextAreaField, FileField, SelectField
from wtforms_alchemy import QuerySelectField
from wtforms.validators import DataRequired

from app.models import Org


class EventForm(FlaskForm):
    event_type = SelectField(u'ประเภทกิจกรรม',
                             choices=[('academic', u'กิจกรรมวิชาการ'),
                                           ('service', u'กิจกรรมบำเพ็ญประโยชน์'),
                                           ('ethics', u'กิจกรรมส่งเสริมจริยธรรม'),
                                           ('amusement', u'กิจกรรมนันทนาการ'),
                                           ('other', u'กิจกรรมอื่นๆ')])
    title = StringField(u'ชื่อกิจกรรม', validators=[DataRequired()])
    desc = TextAreaField(u'รายละเอียด')
    start = DateTimeField(u'เริ่ม', validators=[DataRequired()])
    end = DateTimeField(u'สิ้นสุด', validators=[DataRequired()])
    location = StringField(u'สถานที่', validators=[DataRequired()])
    organiser = QuerySelectField(query_factory=lambda:Org.query.all(),
                                 get_label='name',
                                 label=u'ผู้จัดงาน')
    registration = StringField(u'ช่องทางลงทะเบียน', validators=[DataRequired()])
    upload = FileField(u'อัพโหลดภาพ')
    post_option = SelectField(u'ตัวเลือกเวลาที่ประกาศ',
                             choices=[('postnow', u'ประกาศตอนนี้'),
                                      ('postlater', u'ตั้งเวลาประกาศ')],
                                        default='postlater')
    post_time = DateTimeField(u'เวลาที่ต้องการประกาศ', validators=[DataRequired()])
    remind_option = SelectField(u'แจ้งเตือนก่อนเวลา',
                                choices=[('none', u'ไม่เตือน'),
                                         ('30mins', u'30 นาที'),
                                         ('60mins', u'60 นาที'),
                                         ('1day', u'1 วัน')])



