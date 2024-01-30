# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.audio_visual_unit.models import AVUBorrowReturnServiceDetail
from app.main import db
from app.models import Org
from app.procurement.models import ProcurementDetail

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class CreateRecordForm(ModelForm):
    class Meta:
        model = AVUBorrowReturnServiceDetail
        exclude = ['created_at']


class AddedLenderForm(ModelForm):
    class Meta:
        model = ProcurementDetail

    lender = QuerySelectField(query_factory=lambda: Org.query.all(),
                           get_label='name',
                           label=u'ภาควิชา/หน่วยงาน',
                           blank_text='Select Org..', allow_blank=True)
