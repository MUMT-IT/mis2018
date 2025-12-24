import os
import boto3
from sqlalchemy import func, LargeBinary
import math
from app.main import db
from dateutil.utils import today
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import Province, District, Subdistrict, Zipcode
from app.scb_payment_service.models import ScbPaymentRecord
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
            number = cls(buddhist_year=fiscal_year + 543, code=code, lab=lab, count=0)
            db.session.add(number)
            db.session.commit()
        return number

    @property
    def number(self):
        return u'{}{}{:06}'.format(self.lab.upper(), str(self.buddhist_year)[-2:], self.count + 1)


class ServiceSequenceResultItemID(db.Model):
    __tablename__ = 'service_sequence_result_item_ids'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    result = db.Column('result', db.String(), nullable=False)
    count = db.Column('count', db.Integer, default=0)

    def next(self):
        return u'{}'.format(self.count + 1)

    @classmethod
    def get_number(cls, code, db, result):
        number = cls.query.filter_by(code=code, result=result).first()
        if not number:
            number = cls(code=code, result=result, count=0)
            db.session.add(number)
            db.session.commit()
        return number

    @property
    def number(self):
        return u'{}'.format(self.count + 1)


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


class ServiceSequenceReportLanguageID(db.Model):
    __tablename__ = 'service_sequence_report_language_ids'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    count = db.Column('count', db.Integer, default=0)

    def next(self):
        return u'{}'.format(self.count + 1)

    @classmethod
    def get_number(cls, code, db):
        number = cls.query.filter_by(code=code).first()
        if not number:
            number = cls(code=code, count=0)
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

    @property
    def customer_name(self):
        return self.customer_info.customer_name

    @property
    def contact_email(self):
        return self.customer_info.contact_email

    @property
    def contact_phone_number(self):
        return self.customer_info.contact_phone_number


class ServiceCustomerInfo(db.Model):
    __tablename__ = 'service_customer_infos'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    cus_name = db.Column('cus_name', db.String())
    email = db.Column('email', db.String(), info={'label': 'อีเมล'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(),
                                           info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    fax_no = db.Column('fax_no', db.String(), info={'label': 'fax'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    type_id = db.Column('type_id', db.ForeignKey('service_customer_types.id'))
    type = db.relationship('ServiceCustomerType', backref=db.backref('customers'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('create_customer_account', lazy=True))

    def __str__(self):
        return self.cus_name

    def has_document_address(self):
        for address in self.addresses:
            if address.address_type == 'document':
                return True
                break
        return False

    @property
    def customer_name(self):
        for cus_contact in self.customer_contacts:
            return cus_contact.contact_name

    @property
    def contact_email(self):
        for cus_contact in self.customer_contacts:
            return cus_contact.email

    @property
    def contact_phone_number(self):
        for cus_contact in self.customer_contacts:
            return cus_contact.phone_number


class ServiceCustomerContact(db.Model):
    __tablename__ = 'service_customer_contacts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    contact_name = db.Column('contact_name', db.String(), info={'label': 'ชื่อ-นามสกุล'})
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
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(),
                                           info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    address = db.Column('address', db.String(), info={'label': 'ที่อยู่'})
    province_id = db.Column('province_id', db.ForeignKey('provinces.id'))
    province = db.relationship(Province, backref=db.backref('service_customer_addresses'))
    district_id = db.Column('district_id', db.ForeignKey('districts.id'))
    district = db.relationship(District, backref=db.backref('service_customer_addresses'))
    subdistrict_id = db.Column('subdistrict_id', db.ForeignKey('subdistricts.id'))
    subdistrict = db.relationship(Subdistrict, backref=db.backref('service_customer_addresses'))
    zipcode = db.Column('zipcode', db.String())
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
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
    no = db.Column('no', db.Integer())
    lab = db.Column('lab', db.String())
    code = db.Column('code', db.String())
    image = db.Column('image', db.String())
    service_manual = db.Column('service_manual', db.String())
    service_rate = db.Column('service_rate', db.String())
    phone_number = db.Column('phone_number', db.String())
    email = db.Column('email', db.String())

    def __str__(self):
        return self.code


class ServiceSubLab(db.Model):
    __tablename__ = 'service_sub_labs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sub_lab = db.Column('sub_lab', db.String())
    lab_information = db.Column('lab_information', db.Text(), info={'label': 'ข้อมูลห้องปฏิบัติการทดสอบ'})
    address = db.Column('address', db.Text(), info={'label': 'ที่อยู่'})
    siriraj_address = db.Column('siriraj_address', db.Text(), info={'label': 'ที่อยู่ศิริราช'})
    salaya_address = db.Column('salaya_address', db.Text(), info={'label': 'ที่อยู่ศาลายา'})
    ref = db.Column('ref', db.String())
    code = db.Column('code', db.String())
    sheet = db.Column('sheet', db.String())
    note = db.Column('note', db.String())
    lab_id = db.Column('lab_id', db.ForeignKey('service_labs.id'))
    lab = db.relationship(ServiceLab, backref=db.backref('sub_labs', cascade='all, delete-orphan'))
    assistant_id = db.Column('assistant_id', db.ForeignKey('staff_account.id'))
    assistant = db.relationship(StaffAccount, backref=db.backref('assistants'),
                               foreign_keys=[assistant_id])
    signer_id = db.Column('signer_id', db.ForeignKey('staff_account.id'))
    signer = db.relationship(StaffAccount, backref=db.backref('signer_of_service_requests'), foreign_keys=[signer_id])

    def __str__(self):
        return self.code


class ServiceAppointmentTimeSlot(db.Model):
    __tablename__ = 'service_appointment_time_slots'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    time = db.Column('time', db.String())

    def __str__(self):
        return self.time


class ServiceStatus(db.Model):
    __tablename__ = 'service_statuses'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    status_id = db.Column('status_id', db.Integer())
    admin_status = db.Column('admin_status', db.String())
    customer_status = db.Column('customer_status', db.String())
    admin_status_color = db.Column('admin_status_color', db.String())
    customer_status_color = db.Column('customer_status_color', db.String())

    def __str__(self):
        return f'แอดมิน : {self.admin_status}, ลูกค้า : {self.customer_status}'


class ServiceReportLanguage(db.Model):
    __tablename__ = 'service_report_languages'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    group_id = db.Column('group_id', db.Integer())
    no = db.Column('no', db.Integer())
    type = db.Column('type', db.String())
    thai_language = db.Column('thai_language', db.String())
    eng_language = db.Column('eng_language', db.String())
    language = db.Column('language', db.String())
    category = db.Column('category', db.String())
    item = db.Column('item', db.String())
    price = db.Column('price', db.Numeric())
    sub_lab_id = db.Column('sub_lab_id', db.ForeignKey('service_sub_labs.id'))
    sub_lab = db.relationship(ServiceSubLab, backref=db.backref('report_languages', cascade='all, delete-orphan'))

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
    is_assistant = db.Column('is_assistant', db.Boolean())


class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_no = db.Column('request_no', db.String())
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_accounts.id'))
    customer = db.relationship(ServiceCustomerAccount, backref=db.backref("requests"))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('requests'))
    lab = db.Column('lab', db.String())
    sub_lab_id = db.Column('sub_lab_id', db.ForeignKey('service_sub_labs.id'))
    sub_lab = db.relationship(ServiceSubLab, backref=db.backref("requests"))
    receive_name = db.Column('receive_name', db.String())
    receive_address = db.Column('receive_address', db.String())
    receive_phone_number = db.Column('receive_phone_number', db.String())
    quotation_name = db.Column('quotation_name', db.String())
    quotation_issue_address = db.Column('quotation_issue_address', db.String())
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String())
    quotation_phone_number = db.Column('quotation_phone_number', db.String())
    document_address_id = db.Column('document_address_id', db.ForeignKey('service_customer_addresses.id'))
    document_address = db.relationship(ServiceCustomerAddress, backref=db.backref("document_address_for_requests"),
                                       foreign_keys=[document_address_id])
    quotation_address_id = db.Column('quotation_address_id', db.ForeignKey('service_customer_addresses.id'))
    quotation_address = db.relationship(ServiceCustomerAddress, backref=db.backref("quotation_address_for_requests"),
                                        foreign_keys=[quotation_address_id])
    is_completed = db.Column('is_completed', db.Boolean())
    is_downloaded = db.Column('is_downloaded', db.Boolean())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    status_id = db.Column('status_id', db.ForeignKey('service_statuses.id'))
    status = db.relationship(ServiceStatus, backref=db.backref('requests'))
    data = db.Column('data', JSONB)

    def __str__(self):
        return self.request_no

    def to_dict(self):
        invoice_file = None
        invoice_no = None
        has_invoice = False
        if self.quotations:
            for quotation in self.quotations:
                for invoice in quotation.invoices:
                    if invoice.file_attached_at:
                        invoice_file = invoice.file
                        invoice_no = invoice.invoice_no
                        has_invoice = True
                    else:
                        invoice_file = None
                        invoice_no = None
                        has_invoice = False
        else:
            invoice_file = None
            invoice_no = None
            has_invoice = False

        return {
            'id': self.id,
            'code': self.sub_lab.code if self.sub_lab else None,
            'request_no': self.request_no,
            'created_at': self.created_at,
            'sender': self.customer.customer_info.cus_name if self.customer else None,
            'status_id': self.status.status_id if self.status else None,
            'is_completed': self.is_completed if self.is_completed else None,
            'admin_status': self.status.admin_status if self.status else None,
            'admin_status_color': self.status.admin_status_color if self.status else None,
            'customer_status': self.status.customer_status if self.status else None,
            'quotation_id': [quotation.id for quotation in self.quotations] if self.quotations else None,
            'sample_id': [sample.id for sample in self.samples] if self.samples else None,
            'customer_status_color': self.status.customer_status_color if self.status else None,
            'quotation_sent_at': ', '.join(str(quotation.sent_at) for quotation in self.quotations
                                           if quotation.sent_at) if self.quotations else None,
            'quotation_approved_at': ', '.join(str(quotation.approved_at) for quotation in self.quotations
                                               if quotation.approved_at) if self.quotations else None,
            'quotation_confirmed_at': ', '.join(str(quotation.confirmed_at) for quotation in self.quotations
                                                if quotation.confirmed_at) if self.quotations else None,
            'quotation_cancelled_at': ', '.join(str(quotation.cancelled_at) for quotation in
                                       self.quotations if quotation.cancelled_at) if self.quotations else None,
            'sample_received_at': ', '.join(str(sample.received_at) for sample in self.samples if sample.received_at)
                if self.samples else None,
            'sample_test_at' : ', '.join(str(result.released_at) for result in self.results if result.released_at)
                if self.results else None,
            'result_approved_at': ', '.join(str(result.approved_at) for result in self.results if result.approved_at)
                                    if self.results else None,
            'result_edit_at': ', '.join(str(result.result_edit_at) for result in self.results if result.result_edit_at)
                                if self.results else None,
            'invoice_sent_at': ', '.join(str(invoice.sent_at) for quotation in self.quotations
                                                  if quotation.invoices for invoice in quotation.invoices
                                                  if invoice.sent_at) if self.quotations else None,
            'invoice_head_approved_at': ', '.join(str(invoice.head_approved_at) for quotation in self.quotations
                                                  if quotation.invoices for invoice in quotation.invoices
                                                  if invoice.head_approved_at) if self.quotations else None,
            'invoice_assistant_approved_at': ', '.join(str(invoice.assistant_approved_at) for quotation in self.quotations
                                                  if quotation.invoices for invoice in quotation.invoices
                                                  if invoice.assistant_approved_at) if self.quotations else None,
            'invoice_file_attached_at': ', '.join(str(invoice.file_attached_at) for quotation in self.quotations
                                                  if quotation.invoices for invoice in quotation.invoices
                                                  if invoice.file_attached_at) if self.quotations else None,
            'paid_at': ', '.join(str(payment.paid_at) for quotation in self.quotations
                                                  if quotation.invoices for invoice in quotation.invoices
                                                  if invoice.payments for payment in invoice.payments if payment.paid_at)
                                                    if self.quotations else None,
            'verified_at':  ', '.join(str(payment.verified_at) for quotation in self.quotations
                                                  if quotation.invoices for invoice in quotation.invoices
                                                  if invoice.payments for payment in invoice.payments if payment.verified_at)
                                                    if self.quotations else None,
            'invoice_no': invoice_no,
            'invoice_file': invoice_file,
            'has_invoice': has_invoice,
            'invoice_id': [invoice.id for quotation in self.quotations
                           if quotation.invoices for invoice in quotation.invoices]
                            if self.quotations else None,
            'result_id': [result.id for result in self.results] if self.results else None
        }


class ServiceReqReportLanguageAssoc(db.Model):
    __tablename__ = 'service_req_report_language_assocs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('report_languages', cascade='all, delete-orphan'))
    report_language_id = db.Column('report_language_id', db.ForeignKey('service_report_languages.id'))
    report_language = db.relationship(ServiceReportLanguage, backref=db.backref('requests'))


class ServiceQuotation(db.Model):
    __tablename__ = 'service_quotations'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    quotation_no = db.Column('quotation_no', db.String())
    name = db.Column('name', db.String())
    address = db.Column('address', db.Text())
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String())
    remark = db.Column('remark', db.String())
    reason = db.Column('reason', db.String(), info={'label': 'เหตุผล'})
    other = db.Column('other', db.String(), info={'label': 'รายละเอียดเพิ่มเติม'})
    cancel_reason = db.Column('cancel_reason', db.Text())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('quotations'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('created_quotations'), foreign_keys=[creator_id])
    sent_at = db.Column('sent_at', db.DateTime(timezone=True))
    sender_id = db.Column('sender_id', db.ForeignKey('staff_account.id'))
    sender = db.relationship(StaffAccount, backref=db.backref('sent_quotations'), foreign_keys=[sender_id])
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship(StaffAccount, backref=db.backref('approved_quotations'), foreign_keys=[approver_id])
    confirmed_at = db.Column('confirmed_at', db.DateTime(timezone=True))
    confirmer_id = db.Column('confirmer_id', db.ForeignKey('service_customer_accounts.id'))
    confirmer = db.relationship(ServiceCustomerAccount, backref=db.backref('confirmed_quotations'),
                                foreign_keys=[confirmer_id])
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    canceller_id = db.Column('canceller_id', db.ForeignKey('service_customer_accounts.id'))
    canceller = db.relationship(ServiceCustomerAccount, backref=db.backref('cancelled_quotations'),
                                foreign_keys=[canceller_id])
    digital_signature = db.Column('digital_signature', LargeBinary)

    def to_dict(self):
        return {
            'id': self.id,
            'quotation_no': self.quotation_no,
            'name': self.name,
            'customer_name': self.customer_name,
            'created_at': self.created_at,
            'approved_at': self.approved_at if self.approved_at else None,
            'total_price': '{:,.2f}'.format(self.grand_total()),
            'status_id': self.request.status.status_id if self.request.status else None,
            'customer_status': self.customer_status if self.customer_status else None,
            'customer_status_color': self.customer_status_color if self.customer_status_color else None,
            'admin_status': self.admin_status if self.admin_status else None,
            'admin_status_color': self.admin_status_color if self.admin_status_color else None,
            'creator': self.creator.fullname if self.creator else None,
            'request_no': self.request.request_no if self.request else None,
            'request_id': self.request_id if self.request_id else None,
            'reason': self.reason if self.reason else None,
            'other': self.other if self.other else None
        }

    @property
    def customer_name(self):
        return self.request.customer.customer_name

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

    @property
    def admin_status(self):
        if self.cancelled_at:
            status = 'ลูกค้าไม่ยืนยันใบเสนอราคา'
        elif self.confirmed_at:
            status = 'ลูกค้ายืนยันใบเสนอราคา'
        elif self.approved_at:
            status = 'รอลูกค้ายืนยันใบเสนอราคา'
        elif self.sent_at:
            status = 'รอยืนยันใบเสนอราคา'
        else:
            status = 'ร่างใบเสนอราคา'
        return status

    @property
    def admin_status_color(self):
        if self.cancelled_at:
            color = 'is-danger'
        elif self.confirmed_at:
            color = 'is-success'
        elif self.approved_at:
            color = 'is-primary'
        elif self.sent_at:
            color = 'is-warning'
        else:
            color = 'is-info'
        return color

    @property
    def customer_status(self):
        if self.cancelled_at:
            status = 'ไม่ยืนยัน'
        elif self.confirmed_at:
            status = 'ยืนยัน'
        else:
            status = 'รอยืนยัน'
        return status

    @property
    def customer_status_color(self):
        if self.cancelled_at:
            color = 'is-danger'
        elif self.confirmed_at:
            color = 'is-success'
        else:
            color = 'is-warning'
        return color


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
    appointment_date = db.Column('appointment_date', db.Date(), info={'label': 'วันนัดหมาย'})
    ship_type = db.Column('ship_type', db.String(), info={'label': 'วิธีการส่งตัวอย่าง'})
    location = db.Column('location', db.String())
    location_name = db.Column('location_name', db.String())
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
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    received_at = db.Column('received_at', db.DateTime(timezone=True))
    receiver_id = db.Column('receiver_id', db.ForeignKey('staff_account.id'))
    received_by = db.relationship(StaffAccount, backref=db.backref('receive_sample'), foreign_keys=[receiver_id])
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('samples'))

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_date': self.appointment_date,
            'ship_type': self.ship_type,
            'location_name': self.location_name if self.location_name else None,
            'tracking_number': self.tracking_number,
            'note': self.note if self.note else None,
            'received_at': self.received_at,
            'received_by': self.received_by.fullname if self.received_by else None,
            'request_no': self.request.request_no if self.request else None,
            'sample_condition_status': self.sample_condition_status,
            'sample_condition_status_color': self.sample_condition_status_color,
            'request_id': self.request_id if self.request_id else None,
            'file': self.get_file if self.get_file else None
        }

    @property
    def sample_condition_status(self):
        if self.received_at:
            if (self.sample_integrity == 'ไม่สมบูรณ์' or self.packaging_sealed == 'ปิดไม่สนิท' or
                    self.container_strength == 'ไม่แข็งแรง' or self.container_durability == 'ไม่คงทน' or
                    self.container_damage == 'แตก/หัก' or self.info_match == 'ไม่ตรง' or
                    self.same_production_lot == 'มีชิ้นที่ไม่ใช่รุ่นผลิตเดียวกัน'):
                status = 'ตัวอย่างไม่อยู่ในสภาพสมบูรณ์'
            else:
                status = 'ตัวอย่างอยู่ในสภาพสมบูรณ์'
        else:
            status = None
        return status

    @property
    def sample_condition_status_color(self):
        if self.received_at:
            if (self.sample_integrity == 'ไม่สมบูรณ์' or self.packaging_sealed == 'ปิดไม่สนิท' or
                    self.container_strength == 'ไม่แข็งแรง' or self.container_durability == 'ไม่คงทน' or
                    self.container_damage == 'แตก/หัก' or self.info_match == 'ไม่ตรง' or
                    self.same_production_lot == 'มีชิ้นที่ไม่ใช่รุ่นผลิตเดียวกัน'):
                color = 'is-warning'
            else:
                color = 'is-success'
        else:
            color = 'is-danger'
        return color

    @property
    def get_file(self):
        if self.received_at:
            if (self.has_license == True and self.has_recipe == True):
                status = 'เอกสารครบถ้วน'
                color = 'is-success'
            else:
                status = 'เอกสารไม่ครบถ้วน'
                color = 'is-danger'
        else:
            status = 'ยังไม่ได้ส่งเอกสาร'
            color = 'is-danger'
        return {'status': status, 'color': color}


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
        return {
            'id': self.id,
            'request_id': self.request_id if self.request_id else None,
            'request_no': self.request.request_no if self.request else None,
            'customer': self.customer.customer_info.cus_name if self.customer else None,
            'status_id': self.request.status.status_id if self.request else None,
            'created_at': self.created_at,
            'result_id': [result.id for result in self.request.results] if self.request.results else None,
            'invoice_id': [invoice.id for quotation in self.request.quotations
                           if quotation.confirmed_at for invoice in quotation.invoices]
            if self.request.quotations else None,
            'quotation_id': [quotation.id for quotation in self.request.quotations
                             if quotation.confirmed_at],
        }


class ServiceInvoice(db.Model):
    __tablename__ = 'service_invoices'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    mhesi_no = db.Column('mhesi_no', db.String(), info={'label': 'เลข อว.'})
    invoice_no = db.Column('invoice_no', db.String())
    name = db.Column('name', db.String())
    address = db.Column('address', db.Text())
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('service_invoices'), foreign_keys=[creator_id])
    sent_at = db.Column('sent_at', db.DateTime(timezone=True))
    sender_id = db.Column('sender_id', db.ForeignKey('staff_account.id'))
    sender = db.relationship(StaffAccount, backref=db.backref('sent_invoices'), foreign_keys=[sender_id])
    head_approved_at = db.Column('head_approved_at', db.DateTime(timezone=True))
    head_id = db.Column('head_id', db.ForeignKey('staff_account.id'))
    head = db.relationship(StaffAccount, backref=db.backref('head_approved_invoices'), foreign_keys=[head_id])
    assistant_approved_at = db.Column('assistant_approved_at', db.DateTime(timezone=True))
    assistant_id = db.Column('assistant_id', db.ForeignKey('staff_account.id'))
    assistant = db.relationship(StaffAccount, backref=db.backref('assistant_approved_invoices'),
                                foreign_keys=[assistant_id])
    file = db.Column('file', db.String())
    file_attached_at = db.Column('file_attached_at', db.DateTime(timezone=True))
    file_attached_id = db.Column('file_attached_id', db.ForeignKey('staff_account.id'))
    file_attached_by = db.relationship(StaffAccount, backref=db.backref('file_attached_invoices'),
                                       foreign_keys=[file_attached_id])
    due_date = db.Column('due_date', db.DateTime(timezone=True))
    note = db.Column('note', db.Text())
    verify_at = db.Column('verify_at', db.DateTime(timezone=True))
    verify_id = db.Column('verify_id', db.ForeignKey('staff_account.id'))
    verify_by = db.relationship(StaffAccount, backref=db.backref('verify_invoices'),
                                foreign_keys=[verify_id])
    quotation_id = db.Column('quotation_id', db.ForeignKey('service_quotations.id'))
    quotation = db.relationship(ServiceQuotation, backref=db.backref('invoices', cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_no': self.invoice_no,
            'name': self.name if self.name else None,
            'customer_name': self.customer_name if self.customer_name else None,
            'admin_status': self.admin_status if self.admin_status else None,
            'admin_status_color': self.admin_status_color if self.admin_status_color else None,
            'customer_status': self.customer_status if self.customer_status else None,
            'customer_status_color': self.customer_status_color if self.customer_status_color else None,
            'total_price': '{:,.2f}'.format(self.grand_total),
            'created_at': self.created_at,
            'due_date': self.due_date if self.due_date else None,
            'creator': self.creator.fullname if self.creator else None,
            'file_attached_at': self.file_attached_at if self.file_attached_at else None,
            'assistant_approved_at': self.assistant_approved_at if self.assistant_approved_at else None,
            'payment_type': self.get_payment().payment_type if self.get_payment() else None,
            'paid_at': self.paid_at,
            'amount_paid': self.get_payment().amount_paid if self.get_payment() else None,
            'is_paid': self.is_paid,
            'invoice_file': self.file if self.file else None,
            'receipt_id': [receipt.id for receipt in self.receipts] if self.receipts else None,
            'receipt_no': [receipt.number for receipt in self.receipts] if self.receipts else None,
            'issuer': [receipt.issuer.fullname for receipt in self.receipts] if self.receipts else None,
            'receipt_at': ', '.join(str(receipt.created_datetime) for receipt in
                           self.receipts) if self.receipts else None
        }

    # @property
    # def is_confirmed_payment(self):
    #     total_paid_amount = sum([payment.amount_paid for payment in self.payments if payment.approved_at and not payment.cancelled_at])
    #     return total_paid_amount >= self.grand_total()
    #
    # @property
    # def number_unapproved_payments(self):
    #     return len([payment for payment in self.payments if not payment.approved_at])

    @property
    def customer_name(self):
        return self.quotation.request.customer.customer_name

    @property
    def contact_phone_number(self):
        return self.quotation.request.customer.contact_phone_number

    def get_payment(self):
        payment = self.payments.filter(ServicePayment.created_at != None,
                                       ServicePayment.cancelled_at == None,
                                       ServicePayment.amount_paid == self.grand_total).first()
        if not payment:
            return None
        if payment.payment_type == 'QR Code Payment':
            record = ScbPaymentRecord.query.filter_by(bill_payment_ref1=self.invoice_no).first()
            if record:
                grand_total = float(self.grand_total)
                if math.isclose(grand_total, record.amount):
                    return payment
                else:
                    None
            else:
                return None
        else:
            return payment

    @property
    def paid_at(self):
        return self.get_payment().paid_at.strftime('%d/%m/%Y %H:%M:%S') if self.get_payment() else None

    @property
    def is_paid(self):
        return True if self.get_payment() and self.get_payment().verified_at else False

    @property
    def admin_status(self):
        payment = self.get_payment()
        if payment and payment.verified_at:
            status = 'ชำระเงินแล้ว'
        elif self.paid_at:
            status = 'รอตรวจสอบการชำระเงิน'
        elif self.file_attached_at:
            status = 'ส่งใบแจ้งหนี้แล้ว รอการชำระเงิน'
        elif self.assistant_approved_at:
            status = 'รออัปโหลดใบแจ้งหนี้ฉบับสมบูรณ์'
        elif self.head_approved_at:
            status = 'รอผู้ช่วยคณบดีอนุมัติใบแจ้งหนี้'
        elif self.sent_at:
            status = 'รอหัวหน้าอนุมัติใบแจ้งหนี้'
        else:
            status = 'ร่างใบแจ้งหนี้'
        return status

    @property
    def admin_status_color(self):
        payment = self.get_payment()
        if payment and payment.verified_at:
            color = 'is-success'
        elif self.paid_at:
            color = 'is-warning'
        elif self.file_attached_at:
            color = 'is-link'
        elif self.assistant_approved_at:
            color = 'is-warning'
        elif self.head_approved_at:
            color = 'is-warning'
        elif self.sent_at:
            color = 'is-warning'
        else:
            color = 'is-info'
        return color

    @property
    def customer_status(self):
        payment = self.get_payment()
        if payment and payment.verified_at:
            status = 'ชำระเงินแล้ว'
        elif self.paid_at:
            status = 'รอตรวจสอบการชำระเงิน'
        elif self.file_attached_at:
            status = 'รอการชำระเงิน'
        else:
            status = 'อยู่ระหว่างการจัดทำใบแจ้งหนี้'
        return status

    @property
    def customer_status_color(self):
        payment = self.get_payment()
        if payment and payment.verified_at:
            color = 'is-success'
        elif self.paid_at:
            color = 'is-warning'
        elif self.file_attached_at:
            color = 'is-danger'
        else:
            color = 'is-info'
        return color

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

    @property
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
    payment_type = db.Column('payment_type', db.String(), info={'label': 'วิธีการชำระเงิน',
                                                                'choices': [('', 'กรุณาเลือกวิธีการชำระเงิน'),
                                                                            ('QR Code Payment', 'QR Code Payment'),
                                                                            ('โอนเงิน', 'โอนเงิน'),
                                                                            ('เช็คเงินสด', 'เช็คเงินสด')]
                                                                })
    amount_paid = db.Column('amount_paid', db.Numeric())
    paid_at = db.Column('paid_at', db.DateTime(timezone=True))
    slip = db.Column('slip', db.String())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_accounts.id'))
    customer = db.relationship(ServiceCustomerAccount, backref=db.backref("created_payments"),
                               foreign_keys=[customer_id])
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    canceller_id = db.Column('canceller_id', db.ForeignKey('staff_account.id'))
    canceller = db.relationship(StaffAccount, backref=db.backref('cancelled_payments'), foreign_keys=[canceller_id])
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('created_payments'), foreign_keys=[admin_id])
    verified_at = db.Column('verified_at', db.DateTime(timezone=True))
    verifier_id = db.Column('verifier_id', db.ForeignKey('staff_account.id'))
    verifier = db.relationship(StaffAccount, backref=db.backref('verified_payments'), foreign_keys=[verifier_id])
    invoice_id = db.Column('invoice_id', db.ForeignKey('service_invoices.id'))
    invoice = db.relationship(ServiceInvoice, backref=db.backref('payments', cascade="all, delete-orphan", lazy='dynamic'))

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
    status_id = db.Column('status_id', db.ForeignKey('service_statuses.id'))
    status = db.relationship(ServiceStatus, backref=db.backref('results'))
    released_at = db.Column('released_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    result_edit_at = db.Column('result_edit_at', db.DateTime(timezone=True))
    sent_at = db.Column('sent_at', db.DateTime(timezone=True))
    sender_id = db.Column('sender_id', db.ForeignKey('staff_account.id'))
    sender = db.relationship(StaffAccount, backref=db.backref('sended_results'), foreign_keys=[sender_id])
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('results', cascade="all, delete-orphan"))
    is_sent_email = db.Column('is_sent_email', db.Boolean())
    note = db.Column('note', db.Text())
    is_edited = db.Column('is_edited', db.Boolean())
    status_note = db.Column('status_note', db.Boolean())
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('created_results'), foreign_keys=[creator_id])

    def to_dict(self):
        return {
            'id': self.id,
            'lab_no': self.lab_no,
            'request_no': self.request.request_no if self.request else None,
            'tracking_number': self.tracking_number,
            'status_id': self.request.status.status_id if self.request else None,
            'admin_status': self.admin_status if self.admin_status else None,
            'customer_status': self.customer_status if self.customer_status else None,
            'released_at': self.released_at if self.released_at else None,
            'creator': self.creator.fullname if self.creator else None,
            'request_id': self.request_id if self.request_id else None
        }

    @property
    def get_invoice(self):
        for quotation in self.request.quotations:
            if quotation.confirmed_at and quotation.invoices:
                for invoice in quotation.invoices:
                    total_items = len(invoice.invoice_items)
                    invoice_no = invoice.invoice_no
                    grand_total = invoice.grand_total()
                    due_date = invoice.due_date
                    invoice_id = invoice.id
                    return total_items, invoice_no, grand_total, due_date, invoice_id
        return None

    @property
    def quotation_id(self):
        quotation_id = None
        for quotation in self.request.quotations:
            if quotation.confirmed_at:
                quotation_id = quotation.id
            else:
                quotation_id = None
        return quotation_id

    @property
    def admin_status(self):
        uploaded_all = all(item.draft_file for item in self.result_items)
        if self.approved_at:
            status = 'ยืนยันใบรายงานผลแล้ว'
            color = 'is-success'
        elif self.result_edit_at and not self.approved_at and not self.is_edited:
            status = 'ขอแก้ไขใบรายงานผล'
            color = 'is-info'
        elif uploaded_all and self.sent_at:
            status = 'รอยืนยันใบรายงานผล'
            color = 'is-warning'
        elif uploaded_all and not self.sent_at:
            status = 'รอส่งใบรายงานผล'
            color = 'is-warning'
        elif not uploaded_all:
            status = 'แนบผลบางส่วนแล้ว รอแนบผลที่เหลือ'
            color = 'is-primary'
        else:
            status = 'ยังไม่ดำเนินการทดสอบ'
            color = 'is-danger'
        return {'status': status, 'color': color}

    @property
    def customer_status(self):
        uploaded_all = all(item.draft_file for item in self.result_items)
        if self.request.status.status_id == 22:
            status = 'รายงานพร้อมดาวโหลด'
            color = 'is-success'
        elif self.approved_at:
            status = 'ยืนยันใบรายงานผลแล้ว'
            color = 'is-primary'
        elif self.result_edit_at and not self.approved_at and not self.is_edited:
            status = 'ส่งคำขอแก้ไขใบรายงานผลแล้ว'
            color = 'is-info'
        elif uploaded_all and self.sent_at:
            status = 'รอยืนยันใบรายงานผล'
            color = 'is-warning'
        elif not uploaded_all or (uploaded_all and not self.sent_at):
            status = 'กำลังทดสอบตัวอย่าง'
            color = 'is-light'
        else:
            status = 'ยังไม่ดำเนินการทดสอบ'
            color = 'is-danger'
        return {'status': status, 'color': color}


class ServiceResultItem(db.Model):
    __tablename__ = 'service_result_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sequence = db.Column('sequence', db.String())
    result_id = db.Column('result_id', db.ForeignKey('service_results.id'))
    result = db.relationship(ServiceResult, backref=db.backref('result_items'))
    report_language = db.Column('report_language', db.String())
    url = db.Column('url', db.String())
    draft_file = db.Column('draft_file', db.String())
    final_file = db.Column('final_file', db.String())
    status = db.Column('status', db.String())
    sent_at =  db.Column('sent_at', db.DateTime(timezone=True))
    sender_id = db.Column('sender_id', db.ForeignKey('staff_account.id'))
    sender = db.relationship(StaffAccount, backref=db.backref('sender_results'), foreign_keys=[sender_id])
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    approver_id = db.Column('approver_id', db.ForeignKey('service_customer_accounts.id'))
    approver = db.relationship(ServiceCustomerAccount, backref=db.backref('approver_results'),
                               foreign_keys=[approver_id])
    req_edit_at = db.Column('req_edit_at', db.DateTime(timezone=True))
    edit_requester_id = db.Column('edit_requester_id', db.ForeignKey('service_customer_accounts.id'))
    edit_requester = db.relationship(ServiceCustomerAccount, backref=db.backref('edit_requester_results'),
                                     foreign_keys=[edit_requester_id])
    note = db.Column('note', db.Text())
    edited_at = db.Column('edited_at', db.DateTime(timezone=True))
    is_edited = db.Column('is_edited', db.Boolean())
    released_at = db.Column('released_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('result_items'), foreign_keys=[creator_id])

    def to_dict(self):
        return {
            'id': self.id,
            'result_id': self.result.id if self.result else None,
            'request_no': self.result.request.request_no if self.result else None,
            'tracking_number': self.result.tracking_number if self.result.tracking_number else None,
            'status_id': self.result.status.status_id if self.result else None,
            'admin_status': self.admin_status if self.admin_status else None,
            'customer_status': self.customer_status if self.customer_status else None,
            'sent_at': self.sent_at if self.sent_at else None,
            'report_language': self.report_language if self.report_language else None,
            'note': self.note  if self.note else None,
            'is_edited': self.is_edited if self.is_edited else None,
            'creator': self.creator.fullname if self.creator else None,
            'request_id': self.result.request_id if self.result else None
        }

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

    @property
    def admin_status(self):
        uploaded_all = all(item.draft_file for item in self.result.result_items)
        if self.approved_at:
            status = 'ยืนยันใบรายงานผลแล้ว'
            color = 'is-success'
        elif self.req_edit_at and not self.approved_at and not self.is_edited:
            status = 'ขอแก้ไขใบรายงานผล'
            color = 'is-info'
        elif uploaded_all:
            status = 'รอยืนยันใบรายงานผล'
            color = 'is-warning'
        elif not uploaded_all:
            status = 'แนบผลบางส่วนแล้ว รอแนบผลที่เหลือ'
            color = 'is-primary'
        else:
            status = 'ยังไม่ดำเนินการทดสอบ'
            color = 'is-danger'
        return {'status': status, 'color': color}

    @property
    def customer_status(self):
        uploaded_all = all(item.draft_file for item in self.result.result_items)
        if self.result.request.status.status_id == 22:
            status = 'รายงานพร้อมดาวโหลด'
            color = 'is-success'
        elif self.approved_at:
            status = 'ยืนยันใบรายงานผลแล้ว'
            color = 'is-primary'
        elif self.req_edit_at and not self.approved_at and not self.is_edited:
            status = 'ส่งคำขอแก้ไขใบรายงานผลแล้ว'
            color = 'is-info'
        elif uploaded_all:
            status = 'รอยืนยันใบรายงานผล'
            color = 'is-warning'
        elif not uploaded_all:
            status = 'กำลังทดสอบตัวอย่าง'
            color = 'is-light'
        else:
            status = 'ยังไม่ดำเนินการทดสอบ'
            color = 'is-danger'
        return {'status': status, 'color': color}


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
