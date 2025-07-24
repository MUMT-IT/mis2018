import os
import boto3
from sqlalchemy import func, LargeBinary
from app.main import db
from dateutil.utils import today
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import Province, District, Subdistrict, Zipcode
from app.staff.models import StaffAccount
from sqlalchemy.dialects.postgresql import JSONB

AWS_ACCESS_KEY_ID = os.getenv('BUCKETEER_AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('BUCKETEER_AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('BUCKETEER_AWS_REGION')
S3_BUCKET_NAME = os.getenv('BUCKETEER_BUCKET_NAME')

s3 = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def convert_to_fiscal_year(date):
    if date.month in [10, 11, 12]:
        return date.year + 1
    else:
        return date.year


class ServiceNumberID(db.Model):
    __tablename__ = 'service_number_ids'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    lab = db.Column('lab', db.String(), nullable=False)
    buddhist_year = db.Column('buddhist_year', db.Integer(), nullable=False)
    count = db.Column('count', db.Integer, default=0)
    updated_datetime = db.Column('updated_datetime', db.DateTime(timezone=True))

    def next(self):
        return u'{:02}'.format(self.count + 1)

    @classmethod
    def get_number(cls, code, db, lab, date=today()):
        fiscal_year = convert_to_fiscal_year(date)
        number = cls.query.filter_by(code=code, buddhist_year=fiscal_year + 543, lab=lab).first()
        if not number:
            number = cls(buddhist_year=fiscal_year+543, code=code, lab=lab, count=0)
            db.session.add(number)
            db.session.commit()
        return number

    @property
    def number(self):
        return u'{}/{}{}-{:02}'.format(self.code, self.lab[0:2].upper(), str(self.buddhist_year)[-2:], self.count + 1)


class ServiceSequenceQuotationID(db.Model):
    __tablename__ = 'service_sequence_quotation_ids'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    quotation = db.Column('quotation', db.String(), nullable=False)
    count = db.Column('count', db.Integer, default=0)

    def next(self):
        return u'{}'.format(self.count + 1)

    @classmethod
    def get_number(cls, code, db, quotation):
        number = cls.query.filter_by(code=code, quotation=quotation).first()
        if not number:
            number = cls(code=code, quotation=quotation, count=0)
            db.session.add(number)
            db.session.commit()
        return number

    @property
    def number(self):
        return u'{}'.format(self.count + 1)


class ServiceCustomerAccount(db.Model):
    __tablename__ = 'service_customer_accounts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    display_name = db.Column('display_name', db.String())
    email = db.Column('email', db.String(), unique=True, info={'label': 'อีเมล'})
    __password_hash = db.Column('password', db.String(255), nullable=True)
    verify_datetime = db.Column('verify_datetime', db.DateTime(timezone=True))
    is_first_login = db.Column('is_first_login', db.Boolean())
    customer_info_id = db.Column('customer_info_id', db.ForeignKey('service_customer_infos.id'))
    customer_info = db.relationship('ServiceCustomerInfo', backref=db.backref('accounts', lazy=True))

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
    cus_name = db.Column('cus_name', db.String())
    email = db.Column('email', db.String(), info={'label': 'อีเมล'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(), info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    fax_no = db.Column('fax_no', db.String(), info={'label': 'fax'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    type_id = db.Column('type_id', db.ForeignKey('service_customer_types.id'))
    type = db.relationship('ServiceCustomerType', backref=db.backref('customers'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('create_customer_account', lazy=True))

    def __str__(self):
        return self.cus_name


class ServiceCustomerContact(db.Model):
    __tablename__ = 'service_customer_contacts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    contact_name = db.Column('contact_name', db.String(), info={'label': 'ชื่อผู้ประสานงาน'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    email = db.Column('email', db.String(), info={'label': 'อีเมล'})
    type_id = db.Column('type_id', db.ForeignKey('service_customer_contact_types.id'))
    type = db.relationship('ServiceCustomerContactType', backref=db.backref('customers'))
    remark = db.Column('remark', db.String(), info={'label': 'หมายเหตุ'})
    creator_id = db.Column('creator_id', db.ForeignKey('service_customer_infos.id'))
    creator = db.relationship(ServiceCustomerInfo, backref=db.backref('customer_contacts', lazy=True))

    def __str__(self):
        return self.contact_name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.type if self.type else None,
            'email': self.email,
            'phone_number': self.phone_number,
            'remark': self.remark
        }


class ServiceCustomerAddress(db.Model):
    __tablename__ = 'service_customer_addresses'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_infos.id'))
    customer = db.relationship(ServiceCustomerInfo, backref=db.backref('addresses', cascade='all, delete-orphan'))
    name = db.Column('name', db.String(), info={'label': 'ชื่อ-นามสกุล'})
    address_type = db.Column('address_type', db.String(), info={'label': 'ประเภทที่อยู่'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(), info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    address = db.Column('address', db.String(), info={'label': 'ที่อยู่'})
    province_id = db.Column('province_id', db.ForeignKey('provinces.id'))
    province = db.relationship(Province, backref=db.backref('service_customer_addresses'))
    district_id = db.Column('district_id', db.ForeignKey('districts.id'))
    district = db.relationship(District, backref=db.backref('service_customer_addresses'))
    subdistrict_id = db.Column('subdistrict_id', db.ForeignKey('subdistricts.id'))
    subdistrict = db.relationship(Subdistrict, backref=db.backref('service_customer_addresses'))
    zipcode = db.Column('zipcode', db.String())
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    is_used = db.Column('is_used', db.Boolean())
    remark = db.Column('remark', db.String(), info={'label': 'หมายเหตุ'})

    def __str__(self):
        return (f'{self.name}: {self.taxpayer_identification_no} : {self.address}: {self.subdistrict.name} : '
                f'{self.district.name} : {self.province.name} : {self.zipcode} : {self.phone_number}')


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
    address = db.Column('address', db.Text(), info={'label': 'ที่อยู่'})
    code = db.Column('code', db.String())
    sheet = db.Column('sheet', db.String())
    image = db.Column('image', db.String())
    service_manual = db.Column('service_manual', db.String())
    service_rate = db.Column('service_rate', db.String())
    contact = db.Column('contact', db.String())

    def __str__(self):
        return self.code


class ServiceSubLab(db.Model):
    __tablename__ = 'service_sub_labs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sub_lab = db.Column('sub_lab', db.String())
    address = db.Column('address', db.Text(), info={'label': 'ที่อยู่'})
    short_address = db.Column('short_address', db.Text())
    code = db.Column('code', db.String())
    sheet = db.Column('sheet', db.String())
    image = db.Column('image', db.String())
    service_manual = db.Column('service_manual', db.String())
    service_rate = db.Column('service_rate', db.String())
    contact = db.Column('contact', db.String())
    lab_id = db.Column('lab_id', db.ForeignKey('service_labs.id'))
    lab = db.relationship(ServiceLab, backref=db.backref('sub_labs', cascade='all, delete-orphan'))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship(StaffAccount, backref=db.backref('approver_of_service_requests'), foreign_keys=[approver_id])
    signer_id = db.Column('signer_id', db.ForeignKey('staff_account.id'))
    signer = db.relationship(StaffAccount, backref=db.backref('signer_of_service_requests'), foreign_keys=[signer_id])

    def __str__(self):
        return self.code


class ServiceItem(db.Model):
    __tablename__ = 'service_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    item = db.Column('item', db.String())

    def __str__(self):
        return self.item


class ServiceAdmin(db.Model):
    __tablename__ = 'service_admins'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sub_lab_id = db.Column('sub_lab_id', db.ForeignKey('service_sub_labs.id'))
    sub_lab = db.relationship(ServiceSubLab, backref=db.backref('admins', cascade='all, delete-orphan'))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('lab_admins', cascade='all, delete-orphan'))
    is_central_admin = db.Column('is_central_admin', db.Boolean())
    is_supervisor = db.Column('is_supervisor', db.Boolean())


class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_no = db.Column('request_no', db.String())
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_accounts.id'))
    customer = db.relationship(ServiceCustomerAccount, backref=db.backref("requests"))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('requests'))
    product = db.Column('product', db.String())
    lab = db.Column('lab', db.String())
    document_address_id = db.Column('document_address_id', db.ForeignKey('service_customer_addresses.id'))
    document_address = db.relationship(ServiceCustomerAddress, backref=db.backref("document_address_for_requests"),
                                       foreign_keys=[document_address_id])
    quotation_address_id = db.Column('quotation_address_id', db.ForeignKey('service_customer_addresses.id'))
    quotation_address = db.relationship(ServiceCustomerAddress, backref=db.backref("quotation_address_for_requests"),
                                        foreign_keys=[quotation_address_id])
    agree = db.Column('agree', db.Boolean())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    status = db.Column('status', db.String())
    thai_language = db.Column('thai_language', db.Boolean(), info={'label': 'ใบรายงานผลไทย'})
    eng_language = db.Column('eng_language', db.Boolean(), info={'label': 'ใบรายงานผลอังกฤษ'})
    thai_copy_language = db.Column('thai_copy_language', db.Boolean(), info={'label': 'สำเนาใบรายงานผลไทย'})
    eng_copy_language = db.Column('eng_copy_language', db.Boolean(), info={'label': 'สำเนาใบรายงานผลอังกฤษ'})
    is_paid = db.Column('is_paid', db.Boolean())
    data = db.Column('data', JSONB)

    def __str__(self):
        return self.request_no

    def to_dict(self):
        return {
            'id': self.id,
            'request_no': self.request_no,
            'created_at': self.created_at,
            'product': ", ".join([p.strip().strip('"') for p in self.product.strip("{}").split(",") if p.strip().strip('"')])
                        if self.product else None,
            'sender': self.customer.customer_info.cus_name if self.customer else None,
            'status': self.status
        }


class ServiceQuotation(db.Model):
    __tablename__ = 'service_quotations'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    quotation_no = db.Column('quotation_no', db.String())
    name = db.Column('name', db.String())
    address = db.Column('address', db.Text())
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String())
    status = db.Column('status', db.String())
    remark = db.Column('remark', db.Text())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('quotations'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('created_quotations'), foreign_keys=[creator_id])
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship(StaffAccount, backref=db.backref('approved_quotations'), foreign_keys=[approver_id])
    confirmer_id = db.Column('confirmer_id', db.ForeignKey('service_customer_accounts.id'))
    confirmer = db.relationship(ServiceCustomerAccount, backref=db.backref('confirmed_quotations'), foreign_keys=[confirmer_id])
    digital_signature = db.Column('digital_signature', LargeBinary)

    def to_dict(self):
        return {
            'id': self.id,
            'quotation_no': self.quotation_no,
            'customer': (
                self.request.customer.customer_info.cus_name
                if self.request and self.request.customer and self.request.customer.customer_info
                else None
            ),
            'product': ", ".join(
                [p.strip().strip('"') for p in self.request.product.strip("{}").split(",") if p.strip().strip('"')])
            if self.request else None,
            'status_for_admin': self.get_status_for_admin(),
            'status_for_user': self.get_status_for_user(),
            'status': self.status,
            'created_at': self.created_at,
            'total_price': self.grand_total(),
            'creator': self.creator.fullname if self.creator else None,
            'request_no': self.request.request_no if self.request else None,
            'request_id': self.request_id if self.request_id else None,
        }

    def discount(self):
        discount = 0
        for quotation_item in self.quotation_items:
            if quotation_item.discount:
                if quotation_item.discount_type == 'เปอร์เซ็นต์':
                    amount = quotation_item.total_price * (quotation_item.discount / 100)
                    discount += amount
                else:
                    discount += quotation_item.discount
        return discount

    def subtotal(self):
        total_price = 0
        for quotation_item in self.quotation_items:
            total_price += quotation_item.total_price
        return total_price

    def grand_total(self):
        total_price = 0
        for quotation_item in self.quotation_items:
            if quotation_item.discount:
                if quotation_item.discount_type == 'เปอร์เซ็นต์':
                    discount = quotation_item.total_price * (quotation_item.discount / 100)
                    total_price += quotation_item.total_price - discount
                else:
                    total_price += quotation_item.total_price - quotation_item.discount
            else:
                total_price += quotation_item.total_price
        return total_price

    def get_status_for_admin(self):
        if self.status == 'อยู่ระหว่างการจัดทำใบเสนอราคา':
            color = 'is-light'
        elif self.status == 'รออนุมัติใบเสนอราคาโดยหัวหน้าห้องปฏิบัติการ':
            color = 'is-info'
        elif self.status == 'รอยืนยันใบเสนอราคาจากลูกค้า':
            color = 'is-warning'
        elif self.status == 'ลูกค้าไม่อนุมัติใบเสนอราคา':
            color = 'is-danger'
        else:
            color = 'is-success'
        return f'<span class="tag {color}">{self.status}</span>'

    def get_status_for_user(self):
        if self.status == 'ยืนยันใบเสนอราคาเรียบร้อยแล้ว':
            return '<i class="far fa-check-circle has-text-success"></i>'
        else:
            return '<i class="fas fa-times has-text-danger"></i>'


class ServiceQuotationItem(db.Model):
    __tablename__ = 'service_quotation_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sequence = db.Column('sequence', db.String())
    quotation_id = db.Column('quotation_id', db.ForeignKey('service_quotations.id'))
    quotation = db.relationship(ServiceQuotation, backref=db.backref('quotation_items', cascade="all, delete-orphan"))
    discount_type = db.Column('discount_type', db.String(), info={'label': 'ประเภทส่วนลด',
                                                                  'choices': [('', 'กรุณาเลือกประเภทส่วนลด'),
                                                                              ('เปอร์เซ็นต์', 'เปอร์เซ็นต์'),
                                                                              ('จำนวนเงิน', 'จำนวนเงิน')
                                                                              ]})
    item = db.Column('item', db.String(), nullable=False)
    quantity = db.Column('quantity', db.Integer(), nullable=False)
    unit_price = db.Column('unit_price', db.Numeric(), nullable=False)
    total_price = db.Column('total_price', db.Numeric(), nullable=False)
    discount = db.Column('discount', db.Numeric())

    def net_price(self):
        if self.discount:
            if self.discount_type == 'เปอร์เซ็นต์':
                discount = self.total_price * (self.discount / 100)
                amount = self.total_price - discount
            else:
                amount = self.total_price - self.discount
            return amount
        else:
            return self.total_price

    def get_discount_amount(self):
        if self.discount:
            if self.discount_type == 'เปอร์เซ็นต์':
                discount = self.total_price * (self.discount / 100)
            else:
                discount = self.discount
            return discount
        else:
            return 0


class ServiceSample(db.Model):
    __tablename__ = 'service_samples'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    appointment_date = db.Column('appointment_date', db.DateTime(timezone=True), info={'label': 'วันนัดหมาย'})
    ship_type = db.Column('ship_type', db.String(), info={'label': 'การส่งตัวอย่าง', 'choices': [('None', 'กรุณาเลือกการส่งตัวอย่าง'),
                                                                                                 ('ส่งด้วยตนเอง', 'ส่งด้วยตนเอง'),
                                                                                                 ('ส่งทางไปรษณีย์', 'ส่งทางไปรษณีย์')
                                                                                                 ]})
    location = db.Column('location', db.String(), info={'label': 'สถานที่', 'choices': [('None', 'กรุณาเลือกสถานที่'),
                                                                                        ('ศิริราช', 'ศิริราช'),
                                                                                        ('ศาลายา', 'ศาลายา')
                                                                                        ]})
    tracking_number = db.Column('tracking_number', db.String(), info={'label': 'เลขพัสดุ'})
    sample_integrity = db.Column('sample_integrity', db.String())
    packaging_sealed = db.Column('packaging_sealed', db.String())
    container_strength = db.Column('container_strength', db.String())
    container_durability = db.Column('container_durability', db.String())
    container_damage = db.Column('container_damage', db.String())
    info_match = db.Column('info_match', db.String())
    same_production_lot = db.Column('same_production_lot', db.String())
    has_license = db.Column('has_license', db.Boolean(), default=True)
    has_recipe = db.Column('has_recipe', db.Boolean(), default=True)
    note = db.Column('note', db.Text(), info={'label': 'ข้อมูลเพิ่มเติม'})
    received_at = db.Column('received_at', db.DateTime(timezone=True))
    receiver_id = db.Column('receiver_id', db.ForeignKey('staff_account.id'))
    received_by = db.relationship(StaffAccount, backref=db.backref('receive_sample'), foreign_keys=[receiver_id])
    expected_at = db.Column('expected_at', db.DateTime(timezone=True), info={'label': 'วันที่คาดว่าจะได้รับผล'})
    started_at = db.Column('started_at', db.DateTime(timezone=True))
    starter_id = db.Column('starter_id', db.ForeignKey('staff_account.id'))
    started_by = db.relationship(StaffAccount, backref=db.backref('start_test'), foreign_keys=[starter_id])
    finished_at = db.Column('finished_at', db.DateTime(timezone=True))
    finish_id = db.Column('finish_id', db.ForeignKey('staff_account.id'))
    finished_by = db.relationship(StaffAccount, backref=db.backref('finish_test'), foreign_keys=[finish_id])
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('samples'))

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_date': self.appointment_date,
            'product': ", ".join([p.strip().strip('"') for p in self.request.product.strip("{}").split(",") if p.strip().strip('"')])
                        if self.request else None,
            'ship_type': self.ship_type,
            'location': self.location,
            'tracking_number': self.tracking_number,
            'received_at': self.received_at,
            'received_by': self.received_by.fullname if self.received_by else None,
            'expected_at': self.expected_at,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'finished_by': self.finished_by.fullname if self.finished_by else None,
            'request_no': self.request.request_no if self.request else None,
            'status': self.request.status if self.request else None,
            'request_id': self.request_id if self.request_id else None,
            'quotation_id': [quotation.id for quotation in self.request.quotations if quotation.status == 'ยืนยันใบเสนอราคาเรียบร้อยแล้ว'] if self.request else None
        }


class ServiceTestItem(db.Model):
    __tablename__ = 'service_test_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_accounts.id'))
    customer = db.relationship(ServiceCustomerAccount, backref=db.backref("test_items"))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('test_items'))
    sample_id = db.Column('sample_id', db.ForeignKey('service_samples.id'))
    sample = db.relationship(ServiceSample, backref=db.backref('test_items'))
    status = db.Column('status', db.String())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('test_items'))

    def to_dict(self):
        has_invoice_for_admin = False
        for q in self.request.quotations:
            if q.status == 'ยืนยันใบเสนอราคาเรียบร้อยแล้ว' and q.invoices:
                has_invoice_for_admin = True
            else:
                has_invoice_for_admin = False

        has_invoice_for_user = None
        for q in self.request.quotations:
            if q.status == 'ยืนยันใบเสนอราคาเรียบร้อยแล้ว' and q.invoices:
                for invoice in q.invoices:
                    if invoice.status == 'ออกใบแจ้งหนี้เรียบร้อยแล้ว':
                        has_invoice_for_user = True
                    else:
                        has_invoice_for_user = False
            else:
                has_invoice_for_user = False

        return {
            'id': self.id,
            'request_id': self.request_id if self.request_id else None,
            'request_no': self.request.request_no if self.request else None,
            'customer': self.customer.customer_info.cus_name if self.customer else None,
            'has_invoice_for_admin': has_invoice_for_admin,
            'has_invoice_for_user': has_invoice_for_user,
            'has_result': True if self.request.results else False,
            'request_status': self.request.status if self.request else None,
            'created_at': self.created_at,
            'result_id': [result.id for result in self.request.results] if self.request.results else None,
            'invoice_id': [invoice.id for quotation in self.request.quotations
                           if quotation.status == 'ยืนยันใบเสนอราคาเรียบร้อยแล้ว' for invoice in quotation.invoices]
                            if self.request.quotations else None
        }


class ServiceInvoice(db.Model):
    __tablename__ = 'service_invoices'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    mhesi_no =  db.Column('mhesi_no', db.String(), info={'label': 'เลข อว.'})
    invoice_no = db.Column('invoice_no', db.String())
    name = db.Column('name', db.String())
    address = db.Column('address', db.Text())
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String())
    status = db.Column('status', db.String())
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('service_invoices'))
    due_date = db.Column('due_date', db.DateTime(timezone=True))
    quotation_id = db.Column('quotation_id', db.ForeignKey('service_quotations.id'))
    quotation = db.relationship(ServiceQuotation, backref=db.backref('invoices', cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_no': self.invoice_no,
            'product': ", ".join([p.strip().strip('"') for p in self.quotation.request.product.strip("{}").split(",") if p.strip().strip('"')])
                        if self.quotation else None,
            'status': self.status,
            'total_price': self.grand_total(),
            'created_at': self.created_at,
            'creator': self.creator.fullname if self.creator else None
        }

    def discount(self):
        discount = 0
        for invoice_item in self.invoice_items:
            if invoice_item.discount:
                if invoice_item.discount_type == 'เปอร์เซ็นต์':
                    amount = invoice_item.total_price * (invoice_item.discount / 100)
                    discount += amount
                else:
                    discount += invoice_item.discount
        return discount

    def subtotal(self):
        total_price = 0
        for invoice_item in self.invoice_items:
            total_price += invoice_item.total_price
        return total_price

    def grand_total(self):
        total_price = 0
        for invoice_item in self.invoice_items:
            if invoice_item.discount:
                if invoice_item.discount_type == 'เปอร์เซ็นต์':
                    discount = invoice_item.total_price * (invoice_item.discount / 100)
                    total_price += invoice_item.total_price - discount
                else:
                    total_price += invoice_item.total_price - invoice_item.discount
            else:
                total_price += invoice_item.total_price
        return total_price


class ServiceInvoiceItem(db.Model):
    __tablename__ = 'service_invoice_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sequence = db.Column('sequence', db.String())
    invoice_id = db.Column('invoice_id', db.ForeignKey('service_invoices.id'))
    invoice = db.relationship(ServiceInvoice, backref=db.backref('invoice_items', cascade="all, delete-orphan"))
    discount_type = db.Column('discount_type', db.String())
    item = db.Column('item', db.String(), nullable=False)
    quantity = db.Column('quantity', db.Integer(), nullable=False)
    unit_price = db.Column('unit_price', db.Numeric(), nullable=False)
    total_price = db.Column('total_price', db.Numeric(), nullable=False)
    discount = db.Column('discount', db.Numeric())

    def net_price(self):
        if self.discount:
            if self.discount_type == 'เปอร์เซ็นต์':
                discount = self.total_price * (self.discount / 100)
                amount = self.total_price - discount
            else:
                amount = self.total_price - self.discount
            return amount
        else:
            return self.total_price

    def get_discount_amount(self):
        if self.discount:
            if self.discount_type == 'เปอร์เซ็นต์':
                discount = self.total_price * (self.discount / 100)
            else:
                discount = self.discount
            return discount
        else:
            return 0


class ServicePayment(db.Model):
    __tablename__ = 'service_payments'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    amount_due = db.Column('amount_due', db.Float(), nullable=False)
    status = db.Column('status', db.String())
    paid_at = db.Column('paid_at', db.DateTime(timezone=True))
    bill = db.Column('bill', db.String(255))
    url = db.Column('url', db.String(255))
    sender_id = db.Column('sender_id', db.ForeignKey('service_customer_accounts.id'))
    sender = db.relationship(ServiceCustomerAccount, backref=db.backref('payments'))
    verifier_id = db.Column('verifier_id', db.ForeignKey('staff_account.id'))
    verifier = db.relationship(StaffAccount, backref=db.backref('service_payments'))
    invoice_id = db.Column('invoice_id', db.ForeignKey('service_invoices.id'))
    invoice = db.relationship(ServiceInvoice, backref=db.backref('payments', cascade="all, delete-orphan"))

    def to_dict(self):
        return  {
            'id': self.id,
            'request_id': self.invoice.quotation.request_id if self.invoice else None,
            'product': ", ".join([p.strip().strip('"') for p in self.invoice.quotation.request.product.strip("{}").split(",") if p.strip().strip('"')])
                        if self.invoice else None,
            'amount_due': self.amount_due,
            'status': self.status,
            'paid_at': self.paid_at,
            'sender': self.sender.customer_info.cus_name if self.sender else None,
            'verifier': self.verifier.fullname if self.verifier else None,
            'invoice_no': self.invoice.invoice_no if self.invoice else None
        }


class ServiceReceipt(db.Model):
    __tablename__ = 'service_receipts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    receipt_no = db.Column('receipt_no', db.String(), nullable=False)
    issued_date = db.Column('issued_date', db.DateTime(timezone=True), server_default=func.now())
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('service_receipts'))


class ServiceReceiptItem(db.Model):
    __tablename__ = 'service_receipt_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    receipt_id = db.Column('receipt_id', db.ForeignKey('service_receipts.id'))
    receipt = db.relationship(ServiceReceipt, backref=db.backref('receipt_items', cascade='all, delete-orphan'))
    quantity = db.Column('quantity', db.Integer(), nullable=False)
    unit_price = db.Column('unit_price', db.Float(), nullable=False)
    total_price = db.Column('total_price', db.Float(), nullable=False)


class ServiceResult(db.Model):
    __tablename__ = 'service_results'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    lab_no = db.Column('lab_no', db.String(), unique=True)
    tracking_number = db.Column('tracking_number', db.String(), info={'label': 'เลขพัสดุ'})
    status = db.Column('status', db.String())
    released_at = db.Column('released_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('results', cascade="all, delete-orphan"))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('service_results'))

    def to_dict(self):
        return {
            'id': self.id,
            'lab_no': self.lab_no,
            'request_no': self.request.request_no if self.request else None,
            'tracking_number': self.tracking_number,
            'product': ", ".join([p.strip().strip('"') for p in self.request.product.strip("{}").split(",") if p.strip().strip('"')])
                        if self.request else None,
            'status': self.status,
            'released_at': self.released_at,
            'creator': self.creator.fullname if self.creator else None
        }


class ServiceResultItem(db.Model):
    __tablename__ = 'service_result_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    result_id = db.Column('result_id', db.ForeignKey('service_results.id'))
    result = db.relationship(ServiceResult, backref=db.backref('result_items'))
    report_language = db.Column('report_language', db.String())
    url = db.Column('url', db.String())
    status = db.Column('status', db.String())
    released_at = db.Column('released_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('result_items'))

    @property
    def to_link(self):
        return self.generate_presigned_url(s3, S3_BUCKET_NAME)

    def generate_presigned_url(self):
        if self.url:
            try:
                return s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': S3_BUCKET_NAME, 'Key': self.url},
                    ExpiresIn=3600
                )
            except Exception as e:
                print(f"Error generating presigned URL: {e}")
                return None
        return None


class ServiceOrder(db.Model):
    __tablename__ = 'service_orders'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    service_no = db.Column('service_no', db.String(), nullable=False, unique=True)
    status = db.Column('status', db.String())
    created_datetime = db.Column('created_datetime', db.DateTime(timezone=True), server_default=func.now())
    closed_datetime = db.Column('closed_datetime', db.DateTime(timezone=True))
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_infos.id'))
    customer = db.relationship(ServiceCustomerInfo, backref=db.backref('orders'))
    customer_account_id = db.Column('customer_account_id', db.ForeignKey('service_customer_accounts.id'))
    customer_account = db.relationship(ServiceCustomerAccount, backref=db.backref('orders'))
    lab_id = db.Column('lab_id', db.ForeignKey('service_labs.id'))
    lab = db.relationship(ServiceLab, backref=db.backref('orders'))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('orders'))
    quotation_id = db.Column('quotation_id', db.ForeignKey('service_quotations.id'))
    quotation = db.relationship(ServiceQuotation, backref=db.backref('orders'))
    result_id = db.Column('result_id', db.ForeignKey('service_results.id'))
    result = db.relationship(ServiceResult, backref=db.backref('orders'))
    invoice_id = db.Column('invoice_id', db.ForeignKey('service_invoices.id'))
    invoice = db.relationship(ServiceInvoice, backref=db.backref('orders'))
    payment_id = db.Column('payment_id', db.ForeignKey('service_payments.id'))
    payment = db.relationship(ServicePayment, backref=db.backref('orders'))
    receipt_id = db.Column('receipt_id', db.ForeignKey('service_receipts.id'))
    receipt = db.relationship(ServiceReceipt, backref=db.backref('orders'))


class ServiceProduct(db.Model):
    __tablename__ = 'service_products'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String())
    product_type = db.Column('product_type', db.String())
    test_method = db.Column('test_method', db.String())
    organism = db.Column('organism', db.String())
    type = db.Column('type', db.String())
    carriers = db.Column('carriers', db.Integer())
    is_price_not_one_step = db.Column('is_price_not_one_step', db.Boolean())
    is_price_one_step = db.Column('is_price_one_step', db.Boolean())
    price = db.Column('price', db.Float())