from app.main import db
from werkzeug.security import generate_password_hash, check_password_hash
from app.staff.models import StaffAccount


class ServiceCustomerAccount(db.Model):
    __tablename__ = 'service_customer_accounts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    username = db.Column('username', db.String(),unique=True, info={'label': 'username'})
    email = db.Column('email', db.String(), unique=True, info={'label': 'อีเมล'})
    __password_hash = db.Column('password', db.String(255), nullable=True)
    verify_datetime = db.Column('verify_datetime', db.DateTime(timezone=True))
    customer_info_id = db.Column('customer_info_id', db.ForeignKey('service_customer_infos.id'))
    customer_info = db.relationship("ServiceCustomerInfo", backref=db.backref("account", cascade='all, delete-orphan'))

    def __str__(self):
        return self.email

    def get_id(self):
        return str(self.id)

    def is_active(self):
        return True

    def is_authenticated(self):
        return True

    @property
    def password(self):
        raise AttributeError('Password attribute is not accessible.')

    def verify_password(self, password):
        return check_password_hash(self.__password_hash, password)

    @password.setter
    def password(self, password):
        self.__password_hash  = generate_password_hash(password)


class ServiceCustomerInfo(db.Model):
    __tablename__ = 'service_customer_infos'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    firstname = db.Column('firstname', db.String(), info={'label': 'ชื่อ'})
    lastname = db.Column('lastname', db.String(), info={'label': 'นามสกุล'})
    document_address = db.Column('document_address', db.Text(), info={'label': 'ที่อยู่จัดส่งเอกสาร'})
    quotation_address = db.Column('quotation_address', db.Text(), info={'label': 'ที่อยู่ใบเสนอราคา'})
    telephone = db.Column('telephone', db.String() ,info={'label': 'เบอร์โทรศัพท์'})
    organization_id = db.Column('organization_id', db.ForeignKey('service_customer_organizations.id'))
    organization = db.relationship('ServiceCustomerOrganization', backref=db.backref("info"), foreign_keys=[organization_id])
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('create_customer_account', lazy=True))

    def __str__(self):
        return self.fullname

    @property
    def fullname(self):
        return '{} {}'.format(self.firstname, self.lastname)


class ServiceCustomerOrganization(db.Model):
    __tablename__ = 'service_customer_organizations'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    organization_name = db.Column('organization_name', db.String() ,info={'label': 'บริษัท'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(),
                                           info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    document_address = db.Column('document_address', db.Text(), info={'label': 'ที่อยู่จัดส่งเอกสาร'})
    quotation_address = db.Column('quotation_address', db.Text(), info={'label': 'ที่อยู่ใบเสนอราคา'})
    creator_id = db.Column('creator_id', db.ForeignKey('service_customer_infos.id'))
    creator = db.relationship(ServiceCustomerInfo, backref=db.backref('create_org', lazy=True), foreign_keys=[creator_id])

    def __str__(self):
        return self.organization_name