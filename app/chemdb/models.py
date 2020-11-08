#! -*- coding:utf-8 -*-
from ..main import db
from sqlalchemy.sql import func
from ..staff.models import StaffAccount


class ChemItem(db.Model):
    __tablename__ = 'chemdb_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255), info={'label': u'ชื่อสารเคมี'})
    desc = db.Column('desc', db.String(255), info={'label': u'รายละเอียด'})
    msds = db.Column('msds', db.String(255), info={'label': 'MSDS'})
    cas = db.Column('cas', db.String(255), info={'label': 'CAS'})
    company_code = db.Column('company_code', db.String(255), info={'label': u'รหัสบริษัท'})
    vendor = db.Column('vendor', db.String(255), info={'label': u'ผู้จัดจำหน่าย'})
    container_size = db.Column('container_size', db.Numeric(), info={'label': u'ขนาดบรรจุภัณฑ์'})
    container_unit = db.Column('container_unit', db.String(8), info={'label': u'หน่วย'})
    quantity = db.Column('quantity', db.Integer(), info={'label': u'จำนวน'})
    unit_price = db.Column('unit_price', db.Numeric(), info={'label': u'ราคาต่อหน่วย'})
    expire_date = db.Column('expire_date', db.Date(), info={'label': u'วันหมดอายุ'})
    created_at = db.Column('created_at', db.Date(), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    is_new = db.Column('is_new', db.Boolean())
    location = db.Column('location', db.String(255), info={'label': u'สถานที่เก็บ'})
    contact_id = db.Column('contact_id', db.ForeignKey('staff_account.id'))
    contact = db.relationship(StaffAccount, backref=db.backref('chem_items'))
