# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, TextAreaField, FileField, SelectField, IntegerField
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


class CreateAccountForm(ModelForm):
    class Meta:
        model = PurchaseTrackerAccount
        exclude = ['creation_date', 'end_datetime']
    upload = FileField(u'อัพโหลดไฟล์')

ACTIVITIES = [u'รับเรื่องขออนุมัติหลักการ/ใบเบิก',
                         u'จัดทำ PR ขอซื้อขอจ้าง',
                         u'ขอใบจองงบประมาณ+อนุมัติ A3',
                         u'จัดทำ PO สั่งซื้อสั่งจ้าง/สัญญา',
                         u'บริษัทจัดส่งพัสดุและตรวจรับพัสดุในระบบ MUERP',
                         u'ส่งหน่วยการเงินและบัญชี ตั้งฎีกาเบิกจ่าย']


class StatusForm(ModelForm):
    class Meta:
        model = PurchaseTrackerStatus
        exclude = ['creation_date', 'status_date', 'end_date']
    days = IntegerField(u'ระยะเวลา')
    activity = SelectField(u'กิจกรรม',
                           choices=[(c, c) for c in ACTIVITIES],
                           coerce=unicode,
                           validators=[DataRequired()])
        # field_args = {'desc': {'widget': TextAreaField()}}




