# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import FileField, SelectField, IntegerField, RadioField
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory

from app.main import db
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
    formats = RadioField(u'รูปแบบหลักการ',
                           choices=[(c, c) for c in [u'หลักการตามขั้นตอนปกติ', u'รายงานผลจัดซื้อกรณีจำเป็นเร่งด่วนฯ']],
                           coerce=unicode,
                           validators=[DataRequired()])

ACTIVITIES = [u'รับเรื่องขออนุมัติหลักการ/ใบเบิก',
              u'จัดทำแผน/แต่งตั้งคณะกรรมการกำหนด TOR',
              u'กำหนด TOR',
              u'นำ TOR/SPEC รับฟังความคิดเห็น/พิจารณาความคิดเห็น',
              u'จัดทำรายงานขอซื้อขอจ้าง/PR/แต่งตั้งคณะกรรมการ',
              u'ขอใบจองงบประมาณ+A3',
              u'ประกาศเชิญชวน/เชิญยื่นข้อเสนอ',
              u'พิจารณาผลการจัดซื้อจัดจ้าง/รายงานผลการพิจารณา',
              u'เชิญมาทำสัญญา/ร่างสัญญา',
              u'จัดทำ PO สั่งซื้อสั่งจ้าง/สัญญา',
              u'บริษัทจัดส่งพัสดุ/ตรวจรับพัสดุในระบบ MU-ERP/ระบบ EGP',
              u'รายงานผลตรวจรับ/ขออนุมัติเบิกจ่ายเงิน',
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




