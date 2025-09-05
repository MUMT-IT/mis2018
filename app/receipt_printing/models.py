# -*- coding:utf-8 -*-
from sqlalchemy import func, LargeBinary

from app.academic_services.models import ServiceInvoice
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
    payment_method = db.Column('payment_method', db.String(), nullable=False, info={'label': u'ช่องทางการชำระเงิน',
                                                                                    'choices': [(None, u'--โปรดเลือกช่องทางการชำระเงิน--'),
                                                                                            ('Cash', 'Cash'),
                                                                                            ('Credit Card', 'Credit Card'),
                                                                                            ('QR Payment','QR Payment'),
                                                                                            ('Bank Transfer', 'Bank Transfer'),
                                                                                            ('Cheque', 'Cheque'), ('Other', 'Other')]})
    paid_amount = db.Column('paid_amount', db.Numeric(), default=0.0)
    card_number = db.Column('card_number', db.String(16), info={'label': u'เลขบัตรเครดิต'})
    cheque_number = db.Column('cheque_number', db.String(8), info={'label': u'เช็คเลขที่'})
    other_payment_method = db.Column('other_payment_method', db.String(), info={'label': u'ช่องทางการชำระเงินอื่นๆ'})
    received_money_from_id = db.Column('received_money_from_id', db.ForeignKey('electronic_receipt_received_money_from.id'))
    received_money_from = db.relationship('ElectronicReceiptReceivedMoneyFrom',
                                  backref=db.backref('items_received_from'))
    bank_name_id = db.Column('bank_name_id', db.ForeignKey('electronic_receipt_bank_names.id'))
    bank_name = db.relationship('ElectronicReceiptBankName', backref=db.backref('detail_bank_names'))
    issuer_id = db.Column('issuer_id', db.ForeignKey('staff_account.id'))
    issuer = db.relationship(StaffAccount, foreign_keys=[issuer_id])
    print_number = db.Column('print_number', db.Integer, default=0, info={'label': u'จำนวนพิมพ์'})
    pdf_file = db.Column('pdf_file', LargeBinary)
    invoice_id = db.Column('invoice_id', db.ForeignKey('service_invoices.id'))
    invoice = db.relationship(ServiceInvoice, backref=db.backref('receipts'))

    @property
    def item_list(self):
        return '\n '.join([i.item for i in self.items])

    @property
    def item_gl_list(self):
        return '\n '.join([i.gl.gl for i in self.items])

    @property
    def item_cost_center_list(self):
        return '\n '.join([i.cost_center.id for i in self.items])

    @property
    def item_internal_order_list(self):
        return '\n '.join([i.internal_order_code.id for i in self.items])

    def to_dict(self):
        return {
            'id': self.id,
            'book_number': self.book_number,
            'number': self.number,
            'created_datetime': self.created_datetime,
            'print_number': self.print_number,
            'comment': self.comment,
            'cancelled': self.cancelled,
            'cancel_comment': self.cancel_comment,
            'issuer': self.issuer.personal_info.fullname,
            'paid_amount': self.paid_amount,
            'item_list': self.item_list,
            'item_gl_list': self.item_gl_list,
            'item_cost_center_list': self.item_cost_center_list,
            'item_internal_order_list': self.item_internal_order_list

        }


class ElectronicReceiptItem(db.Model):
    __tablename__ = 'electronic_receipt_items'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    item = db.Column('item', db.Text(), nullable=False, info={'label': u'รายการ'})
    receipt_id = db.Column('receipt_id', db.ForeignKey('electronic_receipt_details.id'))
    receipt_detail = db.relationship('ElectronicReceiptDetail',
                                     backref=db.backref('items', cascade='all, delete-orphan'))
    price = db.Column('price', db.Numeric(), nullable=False, default=0.0, info={'label': u'จำนวนเงิน'})
    cost_center_id = db.Column('cost_center_id', db.ForeignKey('cost_centers.id'))
    cost_center = db.relationship('CostCenter',
                                  backref=db.backref('items_cost_center'))
    iocode_id = db.Column('iocode_id', db.ForeignKey('iocodes.id'))
    internal_order_code = db.relationship('IOCode',
                             backref=db.backref('items_io'))
    gl_id = db.Column('gl_id', db.ForeignKey('electronic_receipt_gls.gl'))
    gl = db.relationship('ElectronicReceiptGL',
                         backref=db.backref('items_gl'))


class ElectronicReceiptRequest(db.Model):
    __tablename__ = 'electronic_receipt_requests'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    detail_id = db.Column('detail_id', db.ForeignKey('electronic_receipt_details.id'))
    detail = db.relationship('ElectronicReceiptDetail',
                             backref=db.backref('reprint_requests', lazy='dynamic'))
    reason = db.Column('reason', db.Text(), nullable=False)
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


class ElectronicReceiptReceivedMoneyFrom(db.Model):
    __tablename__ = 'electronic_receipt_received_money_from'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    received_money_from = db.Column('received_money_from', db.String(), info={'label': u'ได้รับเงินจาก'})
    address = db.Column('address', db.Text())
    taxpayer_dentification_no = db.Column('taxpayer_dentification_no', db.String())

    def __str__(self):
        return u'{}'.format(self.received_money_from)

    def to_dict(self):
        return {
            'id': self.id,
            'received_money_from': self.received_money_from,
            'address': self.address,
            'taxpayer_dentification_no': self.taxpayer_dentification_no
        }


class ElectronicReceiptBankName(db.Model):
    __tablename__ = 'electronic_receipt_bank_names'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    bank_name = db.Column('bank_name', db.String(), info={'label': u'ชื่อธนาคาร'})
    bank_type = db.Column('bank_type', db.String(), info={'label': u'ประเภท'})
    code = db.Column('code', db.String(), info={'label': u'รหัสธนาคาร'})

    def __str__(self):
        return u'{}: {}'.format(self.bank_name, self.bank_type)

