import secrets
import string
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app.main import db

alphabet = string.digits + string.ascii_letters


class ScbPaymentServiceApiClientAccount(db.Model):
    __tablename__ = 'scb_payment_service_client_accounts'
    _account_id = db.Column('account_id', db.String(), nullable=False, primary_key=True)
    _secret_hash = db.Column('secret_hash', db.String(), nullable=False)
    is_active = db.Column('is_active', db.Boolean(), default=True)
    created_at = db.Column('created_at', db.DateTime(timezone=True),
                           server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True),
                           onupdate=func.now())

    @classmethod
    def get_account_by_id(cls, client_id):
        return cls.query.filter_by(_account_id=client_id).first()

    @property
    def account_id(self):
        return self._account_id

    def set_account_id(self):
        self._account_id = ''.join(secrets.choice(string.digits) for i in range(10))

    @property
    def secret(self):
        raise ValueError('Client secret is not accessible.')

    def set_secret(self):
        secret = ''.join(secrets.choice(alphabet) for i in range(32))
        self._secret_hash = generate_password_hash(secret)
        print('The client secret is {}. Please keep it safe.'.format(secret))


class ScbPaymentRecord(db.Model):
    __tablename__ = 'scb_payment_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payer_account_number = db.Column('payer_account_number', db.String())
    payee_proxy_type = db.Column('payee_proxy_type', db.String())
    sending_bank_code = db.Column('send_bank_code', db.String())
    payee_proxy_id = db.Column('payee_proxy_id', db.String())
    bill_payment_ref3 = db.Column('bill_payment_ref3', db.String())
    currency_code = db.Column('currency_code', db.String())
    transaction_type = db.Column('transaction_type', db.String())
    transaction_dateand_time = db.Column('transaction_date_time', db.DateTime(timezone=True))
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
    customer1 = db.Column('customer1', db.String())
    customer2 = db.Column('customer2', db.String())
    service = db.Column('service', db.String())
    created_datetime = db.Column('created_datetime', db.DateTime(timezone=True), server_default=func.now())

    def __str__(self):
        return u'{}: {}:{}'.format(self.payee_name, self.payer_name, self.amount)

    def assign_data_from_request(self, data):
        def camel_to_snake(text):
            new_text = []
            for s in text:
                if s.isupper():
                    new_text.append('_')
                    new_text.append(s.lower())
                else:
                    new_text.append(s)
            return ''.join(new_text)
        for key in data:
            snake_key = camel_to_snake(key)
            try:
                setattr(self, snake_key, data[key])
            except:
                pass
            else:
                print(snake_key, getattr(self, snake_key))

    def to_dict(self):
        return {
            'id': self.id,
            'payer_name': self.payer_name,
            'payee_name': self.payee_name,
            'transaction_dateand_time': self.transaction_dateand_time,
            'bill_payment_ref1': self.bill_payment_ref1,
            'bill_payment_ref2': self.bill_payment_ref2,
            'bill_payment_ref3': self.bill_payment_ref3,
            'amount': self.amount,
            'currency_code': self.currency_code,
            'transaction_id': self.transaction_id,
            'receiving_bank_code': self.receiving_bank_code,
            'sending_bank_code': self.sending_bank_code,
            'payer_account_number': self.payer_account_number,
            'payee_account_number': self.payee_account_number,
            'channel_code': self.channel_code,
            'customer1': self.customer1,
            'customer2': self.customer2,
            'service': self.service

        }
