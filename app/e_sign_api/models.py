from app.staff.models import StaffAccount
from app.main import db
from sqlalchemy import LargeBinary


class CertificateFile(db.Model):
    __tablename__ = 'e_sign_certificate_files'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    file = db.Column('file', LargeBinary)
    image = db.Column('image', LargeBinary)
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('digital_cert_file', uselist=False))
