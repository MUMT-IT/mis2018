from dateutil.utils import today
from sqlalchemy import func, LargeBinary

from ..main import db, ma
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.associationproxy import association_proxy
from marshmallow import fields
from dateutil.relativedelta import relativedelta
from datetime import date, datetime
import pytz


bangkok = pytz.timezone('Asia/Bangkok')


def convert_to_fiscal_year(date):
    if date.month in [10, 11, 12]:
        return date.year + 1
    else:
        return date.year


class SmartNested(fields.Nested):
    def serialize(self, attr, obj, accessor=None):
        if attr not in obj.__dict__:
            return {"id": int(getattr(obj, attr + "_id"))}
        return super(SmartNested, self).serialize(attr, obj, accessor)


profile_service_assoc_table = db.Table('comhealth_profile_service_assoc',
                                       db.Column('profile_id', db.Integer, db.ForeignKey('comhealth_test_profiles.id'),
                                                 primary_key=True),
                                       db.Column('service_id', db.Integer, db.ForeignKey('comhealth_services.id'),
                                                 primary_key=True))

group_service_assoc_table = db.Table('comhealth_group_service_assoc',
                                     db.Column('group_id', db.Integer, db.ForeignKey('comhealth_test_groups.id'),
                                               primary_key=True),
                                     db.Column('service_id', db.Integer, db.ForeignKey('comhealth_services.id'),
                                               primary_key=True))

test_item_record_table = db.Table('comhealth_test_item_records',
                                  db.Column('test_item_id', db.Integer, db.ForeignKey('comhealth_test_items.id'),
                                            primary_key=True),
                                  db.Column('record_id', db.Integer, db.ForeignKey('comhealth_test_records.id'),
                                            primary_key=True),
                                  )

group_customer_table = db.Table('comhealth_group_customers',
                                db.Column('customer_id', db.Integer,
                                          db.ForeignKey('comhealth_customer_groups.id'), primary_key=True),
                                db.Column('group_id', db.Integer,
                                          db.ForeignKey('comhealth_customers.id'), primary_key=True))


class ComHealthInvoice(db.Model):
    __tablename__ = 'comhealth_invoice'
    test_item_id = db.Column('test_item_id', db.Integer,
                             db.ForeignKey('comhealth_test_items.id'),
                             primary_key=True)
    receipt_id = db.Column('receipt_id', db.Integer,
                           db.ForeignKey('comhealth_test_receipts.id'),
                           primary_key=True)
    visible = db.Column('visible', db.Boolean(), default=True)
    reimbursable = db.Column('reimbursable', db.Boolean(), default=True)
    billed = db.Column('billed', db.Boolean(), default=True)
    test_item = db.relationship('ComHealthTestItem',
                                backref=db.backref('invoices', cascade='all, delete-orphan'))
    receipt = db.relationship('ComHealthReceipt',
                              backref=db.backref('invoices', cascade='all, delete-orphan'))


class ComHealthCashier(db.Model):
    __tablename__ = 'comhealth_cashier'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship('StaffAccount', backref=db.backref('comhealth_cashier',
                                                               cascade='all, delete-orphan',
                                                               uselist=False))
    position = db.Column('position', db.String(255))

    @property
    def fullname(self):
        return self.staff.personal_info.fullname

    def __str__(self):
        return self.fullname


class ComHealthOrg(db.Model):
    __tablename__ = 'comhealth_orgs'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255), index=True)

    def __str__(self):
        return u'{}'.format(self.name)


class ComHealthDepartment(db.Model):
    __tablename__ = 'comhealth_department'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255), index=True, nullable=False)
    parent_id = db.Column('parent_id', db.ForeignKey('comhealth_orgs.id'))
    parent = db.relationship('ComHealthOrg',
                             backref=db.backref('departments', cascade='all, delete-orphan'))

    def __str__(self):
        return u'{}'.format(self.name)


class ComHealthDivision(db.Model):
    __tablename__ = 'comhealth_divisions'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255), index=True, nullable=False)
    parent_id = db.Column('parent_id', db.ForeignKey('comhealth_department.id'))
    parent = db.relationship('ComHealthDepartment',
                             backref=db.backref('divisions', cascade='all, delete-orphan'))

    def __str__(self):
        return u'{}'.format(self.name)


class ComHealthCustomer(db.Model):
    __tablename__ = 'comhealth_customers'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    hn = db.Column('hn', db.String(13), unique=True)
    title = db.Column('title', db.String(32))
    firstname = db.Column('firstname', db.String(255), index=True)
    lastname = db.Column('lastname', db.String(255), index=True)
    org_id = db.Column('org_id', db.ForeignKey('comhealth_orgs.id'))
    org = db.relationship('ComHealthOrg', backref=db.backref('employees',
                                                             lazy=True,
                                                             cascade='all, delete-orphan'))
    dept_id = db.Column('dept_id', db.ForeignKey('comhealth_department.id'), nullable=True)
    dept = db.relationship('ComHealthDepartment', backref=db.backref('employees', lazy=True))
    unit = db.Column('unit', db.String())
    dob = db.Column('dob', db.Date())
    gender = db.Column('gender', db.Integer)  # 0 for female, 1 for male
    phone = db.Column('phone', db.String())
    email = db.Column('email', db.String())
    emptype_id = db.Column('emptype_id', db.ForeignKey('comhealth_customer_employment_types.id'))
    emptype = db.relationship('ComHealthCustomerEmploymentType',
                              backref=db.backref('customers'))
    groups = db.relationship('ComHealthCustomerGroup', backref=db.backref('customers'),
                             secondary=group_customer_table)
    line_id = db.Column('line_id', db.String(), unique=True)
    emp_id = db.Column('emp_id', db.String())
    division_id = db.Column('division_id', db.ForeignKey('comhealth_divisions.id'), nullable=True)
    division = db.relationship('ComHealthDivision', backref=db.backref('employees', lazy=True))

    def __str__(self):
        return '{}{} {} {}'.format(self.title, self.firstname,
                                    self.lastname, self.org.name)
    @property
    def gender_text(self):
        if self.gender:
            return 'ชาย/male' if self.gender == 1 else 'หญิง/female'
        return 'ไม่ระบุ/not available'

    def generate_hn(self, force=False):
        if not self.hn or force:
            d = datetime.today().strftime('%y')
            self.hn = '2{}{:04}{:06}'.format(d, self.org_id, self.id)

    @property
    def thai_dob(self):
        if self.dob:
            return '{:02}/{:02}/{}'.format(self.dob.day, self.dob.month, self.dob.year + 543)
        else:
            return None

    def check_login_dob(self, dob):
        return dob == '{:02}{:02}{}'.format(self.dob.day, self.dob.month, self.dob.year + 543)

    @property
    def age(self):
        if self.dob:
            rdelta = relativedelta(date.today(), self.dob)
            return rdelta
        else:
            return None

    @property
    def age_years(self):
        if self.dob:
            rdelta = relativedelta(date.today(), self.dob)
            return rdelta.years
        else:
            return None

    @property
    def fullname(self):
        return u'{}{} {}'.format(self.title, self.firstname, self.lastname)


class ComHealthCustomerEmploymentType(db.Model):
    __tablename__ = 'comhealth_customer_employment_types'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    emptype_id = db.Column('emptype_id', db.String(), nullable=False)
    name = db.Column('name', db.String(), nullable=False)
    finance_comment = db.Column('finance_comment', db.String())

    def __str__(self):
        return self.name


class ComHealthCustomerInfo(db.Model):
    __tablename__ = 'comhealth_customer_info'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    cust_id = db.Column('customer_id', db.ForeignKey('comhealth_customers.id'))
    customer = db.relationship('ComHealthCustomer',
                               backref=db.backref('info',
                                                  cascade='all, delete-orphan',
                                                  lazy=True,
                                                  uselist=False))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    data = db.Column('data', JSONB)

    @property
    def updated_date(self):
        return bangkok.localize(self.updated_at.date())


class ComHealthCustomerInfoItem(db.Model):
    __tablename__ = 'comhealth_customer_info_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    text = db.Column('text', db.String(256), nullable=False)
    dtype = db.Column('type', db.String(64), nullable=False, default='text')
    choices = db.Column('choices', db.Text())
    placeholder = db.Column('placeholder', db.String(64))
    multiple_selection = db.Column('multiple_selection', db.Boolean(), default=False)
    order = db.Column('order', db.Integer, nullable=False)
    unit = db.Column('unit', db.String(32))


class ComHealthCustomerGroup(db.Model):
    __tablename__ = 'comhealth_customer_groups'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(), nullable=False)
    desc = db.Column('desc', db.Text())
    created_at = db.Column('created_at', db.Date(), server_default=func.now())

    def __str__(self):
        return self.name


class ComHealthContainer(db.Model):
    __tablename__ = 'comhealth_containers'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('code', db.String(64), index=True, nullable=False)
    detail = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())
    volume = db.Column('volume', db.Numeric(), default=0)
    group = db.Column('group', db.String())

    def __str__(self):
        return self.name


class ComHealthTest(db.Model):
    __tablename__ = 'comhealth_tests'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(64), index=True, nullable=False, info={'label': 'รหัส'})
    name = db.Column('name', db.String(64), index=True, nullable=False, info={'label': 'ชื่อการทดสอบ'})
    desc = db.Column('desc', db.Text(), info={'label': 'รายละเอียด'})
    gov_code = db.Column('gov_code', db.String(16), info={'label': 'รหัสกรมบัญชีกลาง'})
    default_price = db.Column('default_price', db.Numeric(), default=0, info={'label': 'ราคาตั้งต้น'})
    container_id = db.Column('container_id', db.ForeignKey('comhealth_containers.id'))
    container = db.relationship('ComHealthContainer', backref=db.backref('tests'))
    reimbursable = db.Column('reimbursable', db.Boolean(), default=False, info={'label': 'เบิกได้'})

    def __str__(self):
        return self.name


class ComHealthTestGroup(db.Model):
    __tablename__ = 'comhealth_test_groups'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())
    age_max = db.Column('age_max', db.Integer())
    age_min = db.Column('age_min', db.Integer())
    gender = db.Column('gender', db.Integer())

    def __str__(self):
        return self.name


class ComHealthTestProfile(db.Model):
    __tablename__ = 'comhealth_test_profiles'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())
    age_max = db.Column('age_max', db.Integer())
    age_min = db.Column('age_min', db.Integer())
    gender = db.Column('gender', db.Integer())
    quote = db.Column('quote', db.Numeric())

    def __str__(self):
        return self.name

    def __len__(self):
        return len(self.test_items)

    @property
    def quote_price(self):
        total_price = 0
        if self.quote:
            return self.quote
        else:
            for item in self.test_items:
                total_price += item.price or item.test.default_price
        return total_price


class ComHealthFinanceContactReason(db.Model):
    __tablename__ = 'comhealth_finance_contact_reason'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    reason = db.Column('reason', db.String())


class ComHealthRecord(db.Model):
    __tablename__ = 'comhealth_test_records'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    date = db.Column('date', db.Date())
    labno = db.Column('labno', db.String(16))
    customer_id = db.Column('customer_id', db.ForeignKey('comhealth_customers.id'))
    customer = db.relationship('ComHealthCustomer',
                               backref=db.backref('records', cascade='all, delete-orphan'))
    service_id = db.Column('service_id', db.ForeignKey('comhealth_services.id'))
    service = db.relationship('ComHealthService',
                              backref=db.backref('records',
                                                 cascade='all, delete-orphan',
                                                 lazy='dynamic'))
    checkin_datetime = db.Column('checkin_datetime', db.DateTime(timezone=True))
    ordered_tests = db.relationship('ComHealthTestItem', backref=db.backref('records'),
                                    secondary=test_item_record_table)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    urgent = db.Column('urgent', db.Boolean(), default=False)
    comment = db.Column('comment', db.Text())
    note = db.Column('note', db.Text())
    finance_contact_id = db.Column('finance_contact_id',
                                   db.ForeignKey('comhealth_finance_contact_reason.id'))
    finance_contact = db.relationship(ComHealthFinanceContactReason, backref=db.backref('records'))

    @property
    def container_set(self):
        _containers = set([item.test.container.name for item in self.ordered_tests])
        return _containers

    @property
    def is_checked_in(self):
        return self.checkin_datetime is not None

    def get_container_checkin(self, container_id):
        checkins = [chkin for chkin in self.container_checkins if chkin.container_id == container_id]
        if checkins:
            return checkins[0]

    def to_dict(self):
        return {
            'labno': self.labno,
            'firstname': self.customer.firstname,
            'lastname': self.customer.lastname,
            'checkin_datetime': self.checkin_datetime
        }


class ComHealthTestItem(db.Model):
    __tablename__ = 'comhealth_test_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    test_id = db.Column('test_id', db.ForeignKey('comhealth_tests.id'))
    test = db.relationship('ComHealthTest', backref=db.backref('test_items',
                                                               cascade='all, delete-orphan'))

    profile_id = db.Column('profile_id', db.ForeignKey('comhealth_test_profiles.id'))
    profile = db.relationship('ComHealthTestProfile',
                              backref=db.backref('test_items', cascade='all, delete-orphan'))
    group_id = db.Column('group_id', db.ForeignKey('comhealth_test_groups.id'))
    group = db.relationship('ComHealthTestGroup',
                            backref=db.backref('test_items', cascade='all, delete-orphan'))

    price_ = db.Column('price', db.Numeric())
    receipts = association_proxy('invoices', 'receipt')

    @property
    def price(self):
        if self.price_ is None:
            return self.test.default_price
        else:
            return self.price_

    @price.setter
    def price(self, price):
        self.price_ = price


class ComHealthTestProfileItem(db.Model):
    '''Probably obsolete.
    '''
    __tablename__ = 'comhealth_test_profile_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    record_id = db.Column('record_id', db.ForeignKey('comhealth_test_records.id'))
    profile_id = db.Column('test_id', db.ForeignKey('comhealth_test_profiles.id'))
    profile = db.relationship('ComHealthTestProfile')
    record = db.relationship('ComHealthRecord',
                             backref=db.backref('test_profile_items'))


class ComHealthService(db.Model):
    __tablename__ = 'comhealth_services'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    date = db.Column('date', db.Date())
    location = db.Column('location', db.String(255))
    groups = db.relationship('ComHealthTestGroup', backref=db.backref('services'),
                             secondary=group_service_assoc_table)
    profiles = db.relationship('ComHealthTestProfile', backref=db.backref('services'),
                               secondary=profile_service_assoc_table)

    def __str__(self):
        return u'{} {}'.format(self.date, self.location)


class ComHealthReceiptID(db.Model):
    __tablename__ = 'comhealth_receipt_ids'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    buddhist_year = db.Column('buddhist_year', db.Integer(), nullable=False)
    count = db.Column('count', db.Integer, default=0)
    updated_datetime = db.Column('updated_datetime', db.DateTime(timezone=True))

    # TODO: replace next with next_number
    @property  # decorator
    def next(self):
        return u'{:06}'.format(self.count + 1)

    @classmethod
    def get_number(cls, code, db, date=today()):
        fiscal_year = convert_to_fiscal_year(date)
        number = cls.query.filter_by(code=code, buddhist_year=fiscal_year + 543).first()
        if not number:
            number = cls(buddhist_year=fiscal_year+543, code=code, count=0)
            db.session.add(number)
            db.session.commit()
        return number

    @property
    def number(self):
        return u'{}{}{:06}'.format(self.code, str(self.buddhist_year)[-2:], self.count + 1)


class ComHealthReceipt(db.Model):
    __tablename__ = 'comhealth_test_receipts'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String())
    copy_number = db.Column('copy_number', db.Integer, default=1)
    book_number = db.Column('book_number', db.String(16))
    created_datetime = db.Column('checkin_datetime', db.DateTime(timezone=True))
    record_id = db.Column('record_id', db.ForeignKey('comhealth_test_records.id'))
    record = db.relationship('ComHealthRecord',
                             backref=db.backref('receipts', cascade='all, delete-orphan'))
    tests = association_proxy('invoices', 'test_item')
    comment = db.Column('comment', db.Text())
    paid = db.Column('paid', db.Boolean(), default=False)
    cancelled = db.Column('cancelled', db.Boolean(), default=False)
    cancel_comment = db.Column('cancel_comment', db.Text())
    issuer_id = db.Column('issuer_id', db.ForeignKey('comhealth_cashier.id'))
    issuer = db.relationship('ComHealthCashier',
                             foreign_keys=[issuer_id],
                             backref=db.backref('issued_receipts'))
    issued_at = db.Column('issued_at', db.String())
    cashier_id = db.Column('cashier_id', db.ForeignKey('comhealth_cashier.id'))
    cashier = db.relationship('ComHealthCashier', foreign_keys=[cashier_id])
    payment_method = db.Column('payment_method', db.String(64))
    paid_amount = db.Column('paid_amount', db.Numeric(), default=0.0)
    card_number = db.Column('card_number', db.String(16))
    print_profile_note = db.Column('print_profile_note', db.Boolean(), default=False)
    print_profile_how = db.Column('print_profile_how', db.String(), default=False)
    issued_for = db.Column('issued_for', db.String())
    address = db.Column('address', db.Text())
    pdf_file = db.Column('pdf_file', LargeBinary)


class ComHealthReferenceTestProfile(db.Model):
    """All tests in the profile are reimbursable by the government.
    """
    __tablename__ = 'comhealth_reference_test_profile'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    profile_id = db.Column('profile_id', db.ForeignKey('comhealth_test_profiles.id'))
    profile = db.relationship('ComHealthTestProfile')


class ComHealthSpecimensCheckinRecord(db.Model):
    __tablename__ = 'comhealth_specimens_checkin_records'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    record_id = db.Column('record_id', db.ForeignKey('comhealth_test_records.id'))
    container_id = db.Column('container_id', db.ForeignKey('comhealth_containers.id'))
    checkin_datetime = db.Column('checkin_datetime', db.DateTime(timezone=True), nullable=True)
    record = db.relationship(ComHealthRecord,
                             backref=db.backref('container_checkins', cascade='all, delete-orphan'))
    container = db.relationship(ComHealthContainer,
                                backref=db.backref('checkin_records', cascade='all, delete-orphan'))

    def __init__(self, record_id, container_id, chkdatetime):
        self.record_id = record_id
        self.container_id = container_id
        self.checkin_datetime = chkdatetime


class ComHealthConsentDetail(db.Model):
    __tablename__ = 'comhealth_consent_details'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    details = db.Column('details', db.Text(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    creator = db.Column('creator', db.ForeignKey('staff_account.id'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())


class ComHealthConsentRecord(db.Model):
    __tablename__ = 'comhealth_consent_records'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    consent_date = db.Column('consent_date', db.Date())
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    creator = db.Column('creator', db.ForeignKey('staff_account.id'))
    record_id = db.Column('record_id', db.ForeignKey('comhealth_test_records.id'))
    record = db.relationship(ComHealthRecord, backref=db.backref('consent_record', uselist=False))
    is_consent_given = db.Column('is_consent_given', db.Boolean())
    detail_id = db.Column('detail_id', db.ForeignKey('comhealth_consent_details.id'))


class ComHealthCustomerInfoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ComHealthCustomerInfo


class ComHealthCustomerEmploymentTypeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ComHealthCustomerEmploymentType


class ComHealthCustomerSimpleSchema(ma.SQLAlchemyAutoSchema):
    emptype = fields.Nested(ComHealthCustomerEmploymentTypeSchema(only=('name',)))

    class Meta:
        model = ComHealthCustomer


class ComHealthCustomerSchema(ma.SQLAlchemyAutoSchema):
    info = fields.Nested(ComHealthCustomerInfoSchema)
    emptype = fields.Nested(ComHealthCustomerEmploymentTypeSchema(only=('name',)))

    class Meta:
        model = ComHealthCustomer


class ComHealthReceiptSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ComHealthReceipt


class ComHealthFinanceContactReasonSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ComHealthFinanceContactReason


class ComHealthRecordSchema(ma.SQLAlchemyAutoSchema):
    customer = fields.Nested(ComHealthCustomerSimpleSchema(only=('title', 'firstname',
                                                                 'lastname', 'emptype')))
    finance_contact = fields.Nested(ComHealthFinanceContactReasonSchema(only=('reason',)))
    receipts = fields.List(fields.Nested(ComHealthReceiptSchema(only=('paid', 'cancelled'))))

    class Meta:
        model = ComHealthRecord


class ComHealthRecordCustomerSchema(ma.SQLAlchemyAutoSchema):
    customer = fields.Nested(ComHealthCustomerSchema(only=("id", "firstname", "lastname", "hn")))

    class Meta:
        model = ComHealthRecord


class ComHealthServiceSchema(ma.SQLAlchemyAutoSchema):
    records = fields.Nested(ComHealthRecordSchema, many=True)

    class Meta:
        model = ComHealthService


class ComHealthServiceOnlySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ComHealthService


class ComHealthTestProfileSchema(ma.SQLAlchemyAutoSchema):
    quote = fields.String()

    class Meta:
        model = ComHealthTestProfile


class ComHealthTestGroupSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ComHealthTestGroup


class ComHealthTestSchema(ma.SQLAlchemyAutoSchema):
    default_price = fields.String()

    class Meta:
        model = ComHealthTest


class ComHealthOrgSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ComHealthOrg
