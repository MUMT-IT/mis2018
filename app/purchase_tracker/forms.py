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

ACTIVITIES = [u'รับเรื่องขออนุมัติหลักการ/ใบเบิก ดำเนินการลงรับหนังสือ เสนอหัวหน้าหน่วยพิจารณา',
                         u'ดำเนินการสืบราคา 3 บริษัท(กรณีไม่มีใบเสนอราคาแนบมา)',
                         u'จัดทำ PR ขอซื้อขอจ้าง พร้อมตั้งผุ้ตรวจรับหรือคณะกรรมการตรวจรับพัสดุ ผ่านระบบ MUERP',
                         u'เสนอหัวหน้าหน่วยพัสดุตรวจสอบและอนุมัติ A1 ผ่านระบบ MUERP',
                         u'ขอใบจองงบประมาณจากงานงบประมาณ ผ่านระบบ MUERP',
                         u'เสนอหัวหน้าหน่วยคลังฯตรวจสอบและอนุมัติ A3 ผ่านระบบ MUERP',
                         u'เสนอรองคณบดีฯ, คณบดี ลงนาม',
                         u'เสนอหัวหน้าหน่วยพัสดุตรวจสอบและอนุมัติ A4 ผ่านระบบ MUERP',
                         u'จัดทำ PO สั่งซื้อสั่งจ้าง(บันทึกในระบบเท่านั้น) และเสนอหัวหน้าหน่วยพัสดุตรวจสอบ',
                         u'จัดส่งใบสั่งซื้อให้ทางบริษัท/โทรแจ้งบริษัทจัดส่งพัสดุ',
                         u'บริษัทจัดส่งพัสดุ และทำการตรวจรับพัสดุในระบบ และเวียนลงนามตรวจรับ ผ่านระบบ MUERP',
                         u'เสนอขออนุมัติเบิกจ่าย ผ่านหัวหน้าหน่วยพัสดุ หัวหน้างานคลังฯ รองคณบดีฝ่ายการคลังฯ และคณบดีลงนาม',
                         u'สแกนเอกสารเก็บไฟล์ และส่งเอกสารเพื่อตั้งฎีกาเบิกจ่าย',
                         u'ตั้งฎีกาเบิกจ่าย+เสนอคณบดีลงนามฎีกาเบิกจ่าย+ส่งเอกสารไปกองคลัง ผ่านระบบ MUERP',
                         u'รอเช็คสั่งจ่ายจากกองคลัง ผ่านระบบ MUERP']


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




