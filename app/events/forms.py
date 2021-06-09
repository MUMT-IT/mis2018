# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, TextAreaField
from wtforms_alchemy import QuerySelectField
from wtforms.validators import DataRequired

from app.models import Org


class EventForm(FlaskForm):
    title = StringField(u'ชื่อกิจกรรม', validators=[DataRequired()])
    desc = TextAreaField(u'รายละเอียด')
    start = DateTimeField(u'เริ่ม', validators=[DataRequired()])
    end = DateTimeField(u'สิ้นสุด', validators=[DataRequired()])
    location = StringField(u'สถานที่')
    organiser = QuerySelectField(query_factory=lambda:Org.query.all(),
                                 get_label='name',
                                 label=u'ผู้จัดงาน')
    registration = StringField(u'ช่องทางลงทะเบียน')
    poster = StringField(u'รหัสภาพ poster')

