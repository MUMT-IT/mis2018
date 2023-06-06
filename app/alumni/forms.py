# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import FileField
from wtforms_alchemy import model_form_factory

from app.alumni.models import AlumniInformation
from app.main import db

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class AlumniInformationForm(ModelForm):
    class Meta:
        model = AlumniInformation

    upload = FileField(u'อัพโหลดไฟล์')
