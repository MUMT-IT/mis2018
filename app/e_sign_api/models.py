from app.staff.models import StaffAccount
from app.main import db


class CertificateFile(db.Model):
    __tablename__ = 'e_sign_certificate_files'
    id = db.Column('id', db.Integer(), primary_key=True, autogenerate=True)
    file = db.Column('file', db.BLOB)
    image = db.Column('image', db.BLOB)
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('digital_cert_file', uselist=False))
