from sqlalchemy import func
from app.main import db
from werkzeug.security import generate_password_hash, check_password_hash
from app.staff.models import StaffAccount
from sqlalchemy.dialects.postgresql import JSONB


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
    name = db.Column('name', db.String(), info={'label': 'ชื่อ-นามสกุล'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    email = db.Column('email', db.String(), info={'label': 'อีเมล'})
    type_id = db.Column('type_id', db.ForeignKey('service_customer_contact_types.id'))
    type = db.relationship('ServiceCustomerContactType', backref=db.backref('customers'))
    remark = db.Column('remark', db.String(), info={'label': 'หมายเหตุ'})
    adder_id = db.Column('adder_id', db.ForeignKey('service_customer_accounts.id'))
    adder = db.relationship(ServiceCustomerAccount, backref=db.backref('customer_contacts', lazy=True))

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.type if self.type else None,
            'email': self.email,
            'phone_number': self.phone_number,
            'remark': self.remark
        }


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
    name = db.Column('name', db.String(), info={'label': 'ชื่อ-นามสกุล'})
    address_type = db.Column('address_type', db.String(), info={'label': 'ประเภทที่อยู่'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(), info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    address = db.Column('address', db.Text(), info={'label': 'ที่อยู่'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    remark = db.Column('remark', db.String(), info={'label': 'หมายเหตุ'})
    is_quotation = db.Column('is_quotation', db.Boolean())
    quotation_address_id = db.Column('quotation_address_id', db.ForeignKey('service_customer_quotation_addresses.id'))
    quotation_address = db.relationship('ServiceCustomerQuotationAddress', backref=db.backref('addresses',
                                                                                              cascade='all, delete-orphan'))

    def __str__(self):
        return f'{self.name}: {self.taxpayer_identification_no} : {self.address}: {self.phone_number}'


class ServiceCustomerQuotationAddress(db.Model):
    __tablename__ = 'service_customer_quotation_addresses'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_infos.id'))
    customer = db.relationship(ServiceCustomerInfo, backref=db.backref('quotation_addresses', cascade='all, delete-orphan'))
    bill_name = db.Column('bill_name', db.String(), info={'label': 'ออกในนาม'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String(), info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    quotation_address = db.Column('quotation_address', db.Text(), info={'label': 'ที่อยู่ใบเสนอราคา'})
    phone_number = db.Column('phone_number', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    remark = db.Column('remark', db.String(), info={'label': 'หมายเหตุ'})

    def __str__(self):
        return f'{self.bill_name}: {self.taxpayer_identification_no} : {self.quotation_address}: {self.phone_number}'


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
    code = db.Column('code', db.String())
    sheet = db.Column('sheet', db.String())
    lab_id = db.Column('lab_id', db.ForeignKey('service_labs.id'))
    lab = db.relationship(ServiceLab, backref=db.backref('sub_labs', cascade='all, delete-orphan'))

    def __str__(self):
        return self.code


class ServiceAdmin(db.Model):
    __tablename__ = 'service_admins'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    lab_id = db.Column('lab_id', db.ForeignKey('service_labs.id'))
    lab = db.relationship(ServiceLab, backref=db.backref('admins', cascade='all, delete-orphan'))
    sub_lab_id = db.Column('sub_lab_id', db.ForeignKey('service_sub_labs.id'))
    sub_lab = db.relationship(ServiceSubLab, backref=db.backref('admins', cascade='all, delete-orphan'))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('lab_admins', cascade='all, delete-orphan'))
    is_supervisor = db.Column('is_supervisor', db.Boolean())


class ServiceSampleAppointment(db.Model):
    __tablename__ = 'service_sample_appointments'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    appointment_date = db.Column('appointment_date', db.DateTime(timezone=True), info={'label': 'วันนัดหมาย'})
    ship_type = db.Column('ship_type', db.String(), info={'label': 'การส่งตัวอย่าง', 'choices': [('None', 'การุณาเลือกการส่งตัวอย่าง'),
                                                                                                 ('ส่งด้วยตนเอง', 'ส่งด้วยตนเอง'),
                                                                                                 ('ส่งทางไปรษณีย์', 'ส่งทางไปรษณีย์')
                                                                                                 ]})
    location = db.Column('location', db.String(),
                         info={'label': 'สถานที่', 'choices': [('None', 'การุณาเลือกสถานที่'),
                                                               ('ศิริราช', 'ศิริราช'),
                                                               ('ศาลายา', 'ศาลายา')
                                                               ]})
    received_date = db.Column('received_date', db.DateTime(timezone=True), info={'label': 'วัน-เวลาที่ได้รับผลการทดสอบ'})
    number_of_received_date = db.Column('number_of_received_date', db.Integer(), info={'label': 'จำนวนวันที่ได้รับผลการทดสอบ'})
    sender_id = db.Column('sender_id', db.ForeignKey('service_customer_accounts.id'))
    sender = db.relationship(ServiceCustomerAccount, backref=db.backref('sample_appointments'))
    recipient_id = db.Column('recipient_id', db.ForeignKey('staff_account.id'))
    recipient = db.relationship(StaffAccount, backref=db.backref('sample_appointments'))


class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_no = db.Column('request_no', db.String())
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_infos.id'))
    customer = db.relationship(ServiceCustomerInfo, backref=db.backref("requests"))
    customer_account_id = db.Column('customer_account_id', db.ForeignKey('service_customer_accounts.id'))
    customer_account = db.relationship(ServiceCustomerAccount, backref=db.backref("requests"))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('requests'))
    lab = db.Column('lab', db.String())
    agree = db.Column('agree', db.Boolean())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    status = db.Column('status', db.String())
    data = db.Column('data', JSONB)
    payment_id = db.Column('payment_id', db.ForeignKey('service_payments.id'))
    payment = db.relationship('ServicePayment', backref=db.backref("requests"))
    appointment_id = db.Column('appointment_id', db.ForeignKey('service_sample_appointments.id'))
    appointment = db.relationship('ServiceSampleAppointment', backref=db.backref("requests"))

    def __str__(self):
        return self.request_no

    def to_dict(self):
        return {
            'id': self.id,
            'request_no': self.request_no,
            'created_at': self.created_at,
            'sender': self.customer_account.customer_info.cus_name if self.customer_account else None,
            'status': self.status,
            'quotation_status': [quotation.status for quotation in self.quotations] if self.quotations else None,
            'invoice_no': [invoice.invoice_no for invoice in self.invoices] if self.invoices else None,
            'amount_paid': self.payment.amount_paid if self.payment else None,
            'paid_at': self.payment.paid_at if self.payment else None,
            'payment_id': self.payment_id if self.payment_id else None
        }


class ServiceQuotation(db.Model):
    __tablename__ = 'service_quotations'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    quotation_no = db.Column('quotation_no', db.String())
    total_price = db.Column('total_price', db.Float(), nullable=False)
    status = db.Column('status', db.Boolean(), default=False)
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('quotations'))

    def to_dict(self):
        return {
            'id': self.id,
            'quotation_no': self.quotation_no,
            'request_no': self.request.request_no if self.request else None,
            'total_price':  self.total_price,
            'status': self.status,
            'created_at': self.created_at
        }


class ServiceQuotationItem(db.Model):
    __tablename__ = 'service_quotation_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    quotation_id = db.Column('quotation_id', db.ForeignKey('service_quotations.id'))
    quotation = db.relationship(ServiceQuotation, backref=db.backref('quotation_items', cascade="all, delete-orphan"))
    item = db.Column('item', db.String(), nullable=False)
    quantity = db.Column('quantity', db.Integer(), nullable=False)
    unit_price = db.Column('unit_price', db.Float(), nullable=False)
    total_price = db.Column('total_price', db.Float(), nullable=False)


class ServiceResult(db.Model):
    __tablename__ = 'service_results'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    lab_no = db.Column('lab_no', db.String())
    result_data = db.Column('result_data', db.String())
    result = db.Column('result', JSONB)
    status = db.Column('status', db.String())
    released_at = db.Column('released_at', db.DateTime(timezone=True))
    modified_at = db.Column('modified_at', db.DateTime(timezone=True))
    file_result = db.Column('file_result', db.String(255))
    url = db.Column('url', db.String(255))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('results', cascade="all, delete-orphan"))
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_accounts.id'))
    customer = db.relationship(ServiceCustomerAccount, backref=db.backref('results'))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('service_results'))

    def to_dict(self):
        return {
            'id': self.id,
            'lab_no': self.lab_no,
            'request_no': self.request.request_no if self.request else None,
            'status': self.status,
            'released_at': self.released_at
        }


class ServiceInvoice(db.Model):
    __tablename__ = 'service_invoices'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    invoice_no = db.Column('invoice_no', db.String())
    amount_due = db.Column('amount_due', db.Float(), nullable=False)
    status = db.Column('status', db.String())
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('service_invoices'))
    request_id = db.Column('request_id', db.ForeignKey('service_requests.id'))
    request = db.relationship(ServiceRequest, backref=db.backref('invoices'))

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_no': self.invoice_no,
            'request_no': self.request.request_no if self.request else None,
            'amount_due': self.amount_due,
            'status': self.status,
            'created_at': self.created_at
        }


class ServiceInvoiceItem(db.Model):
    __tablename__ = 'service_invoice_items'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    invoice_id = db.Column('invoice_id', db.ForeignKey('service_invoices.id'))
    invoice = db.relationship(ServiceInvoice, backref=db.backref('invoice_items', cascade="all, delete-orphan"))
    item = db.Column('item', db.String(), nullable=False)
    quantity = db.Column('quantity', db.Integer(), nullable=False)
    unit_price = db.Column('unit_price', db.Float(), nullable=False)
    total_price = db.Column('total_price', db.Float(), nullable=False)


class ServicePayment(db.Model):
    __tablename__ = 'service_payments'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    amount_paid = db.Column('amount_paid', db.Float(), nullable=False)
    status = db.Column('status', db.String())
    paid_at = db.Column('paid_at', db.DateTime(timezone=True))
    bill = db.Column('bill', db.String(255))
    url = db.Column('url', db.String(255))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('service_payments'))
    customer_id = db.Column('customer_id', db.ForeignKey('service_customer_infos.id'))
    customer = db.relationship(ServiceCustomerInfo, backref=db.backref('payments'))
    customer_account_id = db.Column('customer_account_id', db.ForeignKey('service_customer_accounts.id'))
    customer_account = db.relationship(ServiceCustomerAccount, backref=db.backref('payments'))


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
    appointment_id = db.Column('appointment_id', db.ForeignKey('service_sample_appointments.id'))
    appointment = db.relationship(ServiceSampleAppointment, backref=db.backref('orders'))
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