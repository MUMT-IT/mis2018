# -*- coding:utf-8 -*-
from sqlalchemy import func

from app.main import db



class ElectronicReceiptDetail(db.Model):
    __tablename__ = 'electronic_receipt_details'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    number = db.Column('number', db.String(), info={'label': u'เลขที่'})
    copy_number = db.Column('copy_number', db.Integer(), default=1)
    book_number = db.Column('book_number', db.String(), info={'label': u'เล่มที่'})
    created_datetime = db.Column('created_datetime', db.DateTime(timezone=True), default=func.now())
    comment = db.Column('comment', db.Text())
    paid = db.Column('paid', db.Boolean(), default=False)
    cancelled = db.Column('cancelled', db.Boolean(), default=False)
    cancel_comment = db.Column('cancel_comment', db.Text())
    payment_method = db.Column('payment_method', db.String(), info={'label': u'ช่องทางการชำระเงิน',
                                'choices': [(c, c) for c in
                                ['Select..', u'เงินสด', u'บัตรเครดิต', u'Scan QR Code', u'โอนผ่านระบบธนาคารอัตโนมัติ', u'เช็คสั่งจ่าย', u'อื่นๆ' ]]})
    paid_amount = db.Column('paid_amount', db.Numeric(), default=0.0)
    card_number = db.Column('card_number', db.String(16), info={'label': u'เลขบัตรเครดิต'})
    cheque_number = db.Column('cheque_number', db.String(8), info={'label': u'เช็คเลขที่'})
    other_payment_method = db.Column('other_payment_method', db.String(), info={'label': u'ช่องทางการชำระเงินอื่นๆ'})
    address = db.Column('address', db.Text(), info={'label': u'ที่อยู่'})
    received_from = db.Column('received_from', db.String(), info={'label': u'ได้รับเงินจาก'})
    gl = db.Column('gl', db.Integer(), info={'label': u'รหัสบัญชี'})
    cost_center = db.Column('cost_center', db.String(8), info={'label': u'ศูนย์ต้นทุน'})
    internal_order = db.Column('internal_order', db.Integer(), info={'label': 'Internal Order/IO'})
    bank_name = db.Column('bank_name', db.String(), info={'label': u'ชื่อธนาคาร'})


class ElectronicReceiptItem(db.Model):
    __tablename__ = 'electronic_receipt_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    item = db.Column('item', db.String(), info={'label': u'รายการ'})
    receipt_id = db.Column('receipt_id', db.ForeignKey('electronic_receipt_details.id'))
    receipt_detail = db.relationship('ElectronicReceiptDetail',
                           backref=db.backref('items', cascade='all, delete-orphan'))
    price = db.Column('price', db.Numeric(), default=0.0, info={'label': u'จำนวนเงิน'})

