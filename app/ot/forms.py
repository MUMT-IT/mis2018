# -*- coding:utf-8 -*-
from wtforms.validators import DataRequired

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, widgets, BooleanField
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from .models import *
from app.ot.models import (OtPaymentAnnounce)
from app.models import Org

BaseModelForm = model_form_factory(FlaskForm)

class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.sessio


class OtPaymentAnnounceForm(ModelForm):
    class Meta:
        model = OtPaymentAnnounce
        exclude = ['upload_file_url', 'cancelled_at']
        field_args = {'topic': {'validators': [DataRequired()]},
                      'announce_at': {'validators': [DataRequired()]},
                      'start_datetime': {'validators': [DataRequired()]}}

    upload = FileField('File Upload')


class OtCompensationRateForm(ModelForm):
    class Meta:
        model = OtCompensationRate
    announcement = QuerySelectField(u'ประกาศ',
                                get_label='topic',
                                query_factory=lambda: OtPaymentAnnounce.query.all())
    work_at_org = QuerySelectField(get_label='name',
                                    query_factory=lambda: Org.query.all())
    work_for_org = QuerySelectField(u'หน่วยงาน',
                                   get_label='name',
                                   query_factory=lambda: Org.query.all())




