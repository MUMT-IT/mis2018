# -*- coding:utf-8 -*-
from app.main import db


class SCBPaymentRecord(db.Model):
    __tablename__ = 'scb_payment_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payer_account_number = db.Column('payer_account_number', db.String())
    payee_proxy_type = db.Column('payee_proxy_type', db.String())
    sending_bank_code = db.Column('send_bank_code', db.String())
    payee_proxy_id = db.Column('payee_proxy_id', db.String())
    bill_payment_ref3 = db.Column('bill_payment_ref3', db.String())
    currency_code = db.Column('currency_code', db.String())
    transaction_type = db.Column('transaction_type', db.String())
    transaction_date_time = db.Column('transaction_date_time', db.DateTime(timezone=True))
    channel_code = db.Column('channel_code', db.String())
    bill_payment_ref1 = db.Column('bill_payment_ref1', db.String())
    amount = db.Column('amount', db.Float(asdecimal=True))
    payer_proxy_type = db.Column('payer_proxy_type', db.String())
    payee_name = db.Column('payee_name', db.String())
    receiving_bank_code = db.Column('receiveing_bank_code', db.String())
    payee_account_number = db.Column('payee_account_number', db.String())
    payer_proxy_id = db.Column('payer_proxy_id', db.String())
    bill_payment_ref2 = db.Column('bill_payment_ref2', db.String())
    transaction_id = db.Column('transaction_id', db.String())
    payer_name = db.Column('payer_name', db.String())

    def __str__(self):
        return u'{}: {}:{}'.format(self.payee_name, self.payer_name, self.amount)
