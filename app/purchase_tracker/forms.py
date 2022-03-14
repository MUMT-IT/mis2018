# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FileField, IntegerField, RadioField
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.main import db
from app.purchase_tracker.models import PurchaseTrackerAccount, PurchaseTrackerStatus, PurchaseTrackerActivity

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
        exclude = ['creation_date', 'status_date', 'end_date']

    days = IntegerField(u'ระยะเวลา')
    activity = QuerySelectField(u'กิจกรรม',
                                query_factory=lambda: PurchaseTrackerActivity.query.all(),
                                get_label='activity', blank_text='Select category..', allow_blank=False,
                                validators=[DataRequired()])


class CreateActivityForm(ModelForm):
    class Meta:
        model = PurchaseTrackerActivity


