from sqlalchemy import func
from app.main import db
from werkzeug.security import generate_password_hash, check_password_hash
from app.staff.models import StaffAccount
from sqlalchemy.dialects.postgresql import JSONB


class ServiceCustomerAccount(db.Model):
    __tablename__ = 'service_customer_accounts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
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
        self.__password_hash = generate_password_hash(password)


class ServiceCustomerInfo(db.Model):
    __tablename__ = 'service_customer_infos'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), info={'label': 'ชื่อ-นามสกุล'})
    org_name = db.Column('org_name', db.String(), info={'label': 'ชื่อบริษัท'})
    email = db.Column('email', db.String(), info={'label': 'อีเมล'})
    fax_no = db.Column('fax_no', db.String(), info={'label': 'fax'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    type_id = db.Column('type_id', db.ForeignKey('service_customer_types.id'))
    type = db.relationship('ServiceCustomerType', backref=db.backref('customers'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('create_customer_account', lazy=True))

    def __str__(self):
        return self.fullname

    @property
    def fullname(self):
        return '{} {}'.format(self.firstname, self.lastname)


class ServiceCustomerContact(db.Model):
    __tablename__ = 'service_customer_contacts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), info={'label': 'ชื่อ-นามสกุล'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    email = db.Column('email', db.String(), info={'label': 'อีเมล'})
    type_id = db.Column('type_id', db.ForeignKey('service_customer_contact_types.id'))
    type = db.relationship('ServiceCustomerContactType', backref=db.backref('customers'))
    remark = db.Column('remark', db.String(), info={'label': 'หมายเหตุ'})
    adder_id = db.Column('adder_id', db.ForeignKey('service_customer_infos.id'))
    adder = db.relationship(ServiceCustomerInfo, backref=db.backref('customer_contacts', lazy=True))

    def __str__(self):
        return self.fullname

    @property
    def fullname(self):
        return '{} {}'.format(self.firstname, self.lastname)


class ServiceCustomerOrganization(db.Model):
    __tablename__ = 'service_customer_organizations'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    organization_name = db.Column('organization_name', db.String(), info={'label': 'บริษัท'})
    creator_id = db.Column('creator_id', db.ForeignKey('service_customer_infos.id'))
    creator = db.relationship(ServiceCustomerInfo, backref=db.backref('create_org', lazy=True), foreign_keys=[creator_id])
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('org_of_customer', lazy=True))

    def __str__(self):
        return self.organization_name


class ServiceCustomerAddress(db.Model):
    __tablename__ = 'service_customer_addresses'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_infos.id'))
    customer = db.relationship(ServiceCustomerInfo, backref=db.backref('addresses', cascade='all, delete-orphan'))
    bill_name = db.Column('bill_name', db.String(), info={'label': 'ออกในนาม'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(), info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    document_address = db.Column('document_address', db.Text(), info={'label': 'ที่อยู่จัดส่งเอกสาร'})
    quotation_address = db.Column('quotation_address', db.Text(), info={'label': 'ที่อยู่ใบเสนอราคา'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    remark = db.Column('remark', db.String(), info={'label': 'หมายเหตุ'})


class ServiceCustomerType(db.Model):
    __tablename__ = 'service_customer_types'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    type = db.Column('type', db.String())

    def __str__(self):
        return self.type


class ServiceCustomerContactType(db.Model):
    __tablename__ = 'service_customer_contact_types'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    type = db.Column('type', db.String())

    def __str__(self):
        return self.type


class ServiceLab(db.Model):
    __tablename__ = 'service_labs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    lab = db.Column('lab', db.String())
    code = db.Column('code', db.String())

    def __str__(self):
        return self.code


class ServiceSubLab(db.Model):
    __tablename__ = 'service_sub_labs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sub_lab = db.Column('sub_lab', db.String())
    code = db.Column('code', db.String())
    lab_id = db.Column('lab_id', db.ForeignKey('service_labs.id'))
    lab = db.relationship(ServiceLab, backref=db.backref('sub_labs', cascade='all, delete-orphan'))

    def __str__(self):
        return self.code


class ServiceAdmin(db.Model):
    __tablename__ = 'service_admins'
    lab_id = db.Column(db.ForeignKey('service_labs.id'), primary_key=True)
    lab = db.relationship(ServiceLab, backref=db.backref('admins', cascade='all, delete-orphan'))
    admin_id = db.Column(db.ForeignKey('staff_account.id'), primary_key=True)
    admin = db.relationship(StaffAccount, backref=db.backref('admin_labs'))


class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_infos.id'))
    customer = db.relationship(ServiceCustomerInfo, backref=db.backref("requests"))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('requests'))
    lab = db.Column('lab', db.String())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    data = db.Column('data', JSONB)

    def to_dict(self):
        product = []
        for value in self.data:
            if isinstance(value, list) and len(value) > 1:
                if value[0] == 'ข้อมูลผลิตภัณฑ์':
                    for v in value[1]:
                        if isinstance(v, list) and v[0] == 'ชื่อผลิตภัณฑ์':
                            product = v[1]
        return {
            'id': self.id,
            'created_at': self.created_at,
            'sender': self.customer.fullname,
            'product': [product]
        }


class ServiceQuotation(db.Model):
    __tablename__ = 'service_quotations'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    total_price = db.Column('total_price', db.Float(), nullable=False)
    status = db.Column('status', db.Boolean(), default=False)


class ServiceSampleAppointment(db.Model):
    __tablename__ = 'service_sample_appointments'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    appointment_date = db.Column('appointment_date', db.DateTime(timezone=True), info={'label': 'วัดนัดหมาย'})
    note = db.Column('note', db.Text(), info={'label', 'รายละเอียดเพิ่มเติม'})


class ServiceResult(db.Model):
    __tablename__ = 'service_results'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    result_data = db.Column('result_data', db.String())
    status = db.Column('status', db.String())
    released_at = db.Column('released_at', db.DateTime(timezone=True))