# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, TextAreaField, FileField, SelectField
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory
from wtforms_alchemy import QuerySelectField

from app.main import db
from app.models import Org
from app.purchase_tracker.models import PurchaseTrackerAccount, PurchaseTrackerStatus

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class RegisterAccountForm(ModelForm):
    class Meta:
        model = PurchaseTrackerAccount
        exclude = ['creation_date']
        # field_args = {'desc': {'widget': TextAreaField()}}

    upload = FileField(u'อัพโหลดไฟล์')
    organiser = QuerySelectField(query_factory=lambda: Org.query.all(),
                                 get_label='name',
                                 label=u'องค์กร/หน่วยงาน')
    status = QuerySelectField(u'สถานะ', query_factory=lambda: PurchaseTrackerStatus.query.all(), get_label='status',
                                blank_text='Select status..', allow_blank=False)


