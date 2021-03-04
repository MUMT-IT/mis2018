# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.main import db
from models import EduQAProgram
from app.staff.models import StaffAcademicPositionRecord, StaffAcademicPosition

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ProgramForm(ModelForm):
    class Meta:
        model = EduQAProgram


class AcademicPositionRecordForm(ModelForm):
    class Meta:
        model = StaffAcademicPositionRecord
    position = QuerySelectField(u'ตำแหน่ง',
                                get_label='fullname_th',
                                query_factory=lambda: StaffAcademicPosition.query.all())