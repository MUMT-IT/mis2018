# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField
from wtforms.validators import DataRequired


class EventForm(FlaskForm):
    title = StringField(u'ชื่อกิจกรรม', validators=[DataRequired()])
    start = DateTimeField(u'เริ่ม', validators=[DataRequired()])
    end = DateTimeField(u'สิ้นสุด', validators=[DataRequired()])
