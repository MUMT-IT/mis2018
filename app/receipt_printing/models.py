# -*- coding:utf-8 -*-
from sqlalchemy import func

from app.main import db
from app.staff.models import StaffAccount


class ElectronicReceiptDetail(db.Model):
    __tablename__ = 'electronic_receipt_details'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
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
    bank_name = db.Column('bank_name', db.String(), info={'label': u'ชื่อธนาคาร'})
    issuer_id = db.Column('issuer_id', db.ForeignKey('staff_account.id'))
    issuer = db.relationship(StaffAccount, foreign_keys=[issuer_id])
    print_number = db.Column('print_number', db.Integer, default=0, info={'label': u'จำนวนพิมพ์'})

    @property
    def item_list(self):
        return ', '.join([i.item for i in self.items])

    def to_dict(self):
        return {
            'id': self.id,
            'book_number': self.book_number,
            'number': self.number,
            'created_datetime': self.created_datetime,
            'print_number': self.print_number,
            'comment': self.comment,
            'cancelled': self.cancelled,
            'cancel_comment': self.cancel_comment
        }


class ElectronicReceiptItem(db.Model):
    __tablename__ = 'electronic_receipt_items'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    item = db.Column('item', db.String(), info={'label': u'รายการ'})
    receipt_id = db.Column('receipt_id', db.ForeignKey('electronic_receipt_details.id'))
    receipt_detail = db.relationship('ElectronicReceiptDetail',
                           backref=db.backref('items', cascade='all, delete-orphan'))
    price = db.Column('price', db.Numeric(), default=0.0, info={'label': u'จำนวนเงิน'})
    cost_center = db.Column('cost_center', db.String(), info={'label': u'ศูนย์ต้นทุน'})
    internal_order = db.Column('internal_order', db.String(), info={'label': 'Internal Order/IO'})
    gl_id = db.Column('gl_id', db.ForeignKey('electronic_receipt_gls.gl'))
    gl = db.relationship('ElectronicReceiptGL',
                         backref=db.backref('items_gl'))


class ElectronicReceiptRequest(db.Model):
    __tablename__ = 'electronic_receipt_requests'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    detail_id = db.Column('detail_id', db.ForeignKey('electronic_receipt_details.id'))
    detail = db.relationship('ElectronicReceiptDetail',
                             backref=db.backref('reprint_requests', lazy='dynamic'))
    reason = db.Column('reason', db.Text())
    url_drive = db.Column('url_drive', db.String())
    created_at = db.Column('created_at', db.Date(), server_default=func.now())
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, foreign_keys=[staff_id])


class ElectronicReceiptGL(db.Model):
    __tablename__ = 'electronic_receipt_gls'
    gl = db.Column('gl', db.String(), primary_key=True, nullable=False, info={'label': u'รหัสบัญชี'})
    receive_name = db.Column('receive_name', db.String())

    def __str__(self):
        return u'{}: {}'.format(self.gl, self.receive_name)


