import secrets
import string
from sqlalchemy import func
from werkzeug import generate_password_hash, check_password_hash

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
