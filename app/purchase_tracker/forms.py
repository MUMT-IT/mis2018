# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FileField, IntegerField, RadioField, StringField, FormField
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.main import db
from app.models import Org
from app.purchase_tracker.models import PurchaseTrackerAccount, PurchaseTrackerStatus, PurchaseTrackerActivity, \
    PurchaseTrackerForm

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class CreateAccountForm(ModelForm):
    class Meta:
        model = PurchaseTrackerAccount
        exclude = ['creation_date', 'end_datetime']

    upload = FileField(u'อัพโหลดไฟล์')
    formats = RadioField(u'รูปแบบหลักการ',
                         choices=[(c, c) for c in [u'หลักการตามขั้นตอนปกติ', u'รายงานผลจัดซื้อกรณีจำเป็นเร่งด่วนฯ']],
                         coerce=unicode,
                         validators=[DataRequired()])


class StatusForm(ModelForm):
    class Meta:
        model = PurchaseTrackerStatus
        exclude = ['creation_date', 'status_date']

    days = IntegerField(u'ระยะเวลา')
    activity = QuerySelectField(u'กิจกรรม',
                                query_factory=lambda: PurchaseTrackerActivity.query.all(),
                                get_label='activity', blank_text='Select activities..', allow_blank=True)


class CreateActivityForm(ModelForm):
    class Meta:
        model = PurchaseTrackerActivity


class ReportDateForm(FlaskForm):
   start_date = StringField(u'วันที่เริ่มต้น')
   end_date = StringField(u'วันที่สิ้นสุด')


class CreateMTPCForm(ModelForm):
    class Meta:
        model = PurchaseTrackerForm

        org = QuerySelectField(query_factory=lambda: Org.query.all(),
                               get_label='name',
                               label=u'ภาควิชา/หน่วยงาน')
        account = FormField(CreateAccountForm, default=acnt)
    return CreateMTPCForm
