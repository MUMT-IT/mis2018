from ..main import db, ma
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.associationproxy import association_proxy
from marshmallow import fields
from dateutil.relativedelta import relativedelta
from datetime import date
import pytz

bangkok = pytz.timezone('Asia/Bangkok')

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
'''
test_item_receipt_table = db.Table('comhealth_test_item_receipts',
                                  db.Column('test_item_id', db.Integer, db.ForeignKey('comhealth_test_items.id'),
                                            primary_key=True),
                                  db.Column('receipt_id', db.Integer,
                                            db.ForeignKey('comhealth_test_receipts.id'),
                                            primary_key=True),
                                  )
'''


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
    test_item = db.relationship('ComHealthTestItem', backref='invoices')
    receipt = db.relationship('ComHealthReceipt', backref='invoices')


class ComHealthCashier(db.Model):
    __tablename__ = 'comhealth_cashier'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    firstname = db.Column('firstname', db.String(255), index=True)
    lastname = db.Column('lastname', db.String(255), index=True)
    position = db.Column('position', db.String(255))

    @property
    def fullname(self):
        return u'{} {}'.format(self.firstname, self.lastname)

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
    parent = db.relationship('ComHealthOrg', backref=db.backref('departments'))

    def __str__(self):
        return u'{}'.format(self.name)


class ComHealthCustomer(db.Model):
    __tablename__ = 'comhealth_customers'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    title = db.Column('title', db.String(32))
    firstname = db.Column('firstname', db.String(255), index=True)
    lastname = db.Column('lastname', db.String(255), index=True)
    org_id = db.Column('org_id', db.ForeignKey('comhealth_orgs.id'))
    org = db.relationship('ComHealthOrg', backref=db.backref('employees', lazy=True))
    dob = db.Column('dob', db.Date())
    gender = db.Column('gender', db.Integer)  # 0 for female, 1 for male
    emptype_id = db.Column('emptype_id', db.ForeignKey('comhealth_customer_employment_types.id'))
    emptype = db.relationship('ComHealthCustomerEmploymentType',
                              backref=db.backref('customers'))

    def __str__(self):
        return u'{}{} {} {}'.format(self.title, self.firstname,
                                    self.lastname, self.org.name)

    @property
    def thai_dob(self):
        return u'{}/{}/{}'.format(self.dob.day, self.dob.month, self.dob.year + 543)

    @property
    def age(self):
        if self.dob:
            rdelta = relativedelta(date.today(), self.dob)
            return rdelta
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

    def __str__(self):
        return self.name


class ComHealthCustomerInfo(db.Model):
    __tablename__ = 'comhealth_customer_info'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    cust_id = db.Column('customer_id', db.ForeignKey('comhealth_customers.id'))
    customer = db.relationship('ComHealthCustomer',
                    backref=db.backref('info', lazy=True, uselist=False))
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


class ComHealthContainer(db.Model):
    __tablename__ = 'comhealth_containers'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('code', db.String(64), index=True, nullable=False)
    detail = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())
    volume = db.Column('volume', db.Numeric(), default=0)


    def __str__(self):
        return self.name


class ComHealthTest(db.Model):
    __tablename__ = 'comhealth_tests'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(64), index=True, nullable=False)
    name = db.Column('name', db.String(64), index=True, nullable=False)
    desc = db.Column('desc', db.Text())
    gov_code = db.Column('gov_code', db.String(16))
    default_price = db.Column('default_price', db.Numeric(), default=0)
    container_id = db.Column('container_id', db.ForeignKey('comhealth_containers.id'))
    container = db.relationship('ComHealthContainer', backref=db.backref('tests'))

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

    @property
    def quote_price(self):
        total_price = 0
        if self.quote:
            return self.quote
        else:
            for item in self.test_items:
                total_price += item.price or item.test.default_price
        return total_price


class ComHealthRecord(db.Model):
    __tablename__ = 'comhealth_test_records'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    date = db.Column('date', db.Date())
    labno = db.Column('labno', db.String(16))
    customer_id = db.Column('customer_id', db.ForeignKey('comhealth_customers.id'))
    customer = db.relationship('ComHealthCustomer', backref=db.backref('records'))
    service_id = db.Column('service_id', db.ForeignKey('comhealth_services.id'))
    service = db.relationship('ComHealthService', backref=db.backref('records'))
    checkin_datetime = db.Column('checkin_datetime', db.DateTime(timezone=True))
    ordered_tests = db.relationship('ComHealthTestItem', backref=db.backref('records'),
                                    secondary=test_item_record_table)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    urgent = db.Column('urgent', db.Boolean(), default=False)
    comment = db.Column('comment', db.Text())

    @property
    def container_set(self):
        _containers = set([item.test.container.name for item in self.ordered_tests])
        return _containers

    @property
    def is_checked_in(self):
        return self.checkin_datetime is not None


class ComHealthTestItem(db.Model):
    __tablename__ = 'comhealth_test_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    test_id = db.Column('test_id', db.ForeignKey('comhealth_tests.id'))
    test = db.relationship('ComHealthTest')

    profile_id = db.Column('profile_id', db.ForeignKey('comhealth_test_profiles.id'))
    profile = db.relationship('ComHealthTestProfile', backref=db.backref('test_items'))
    group_id = db.Column('group_id', db.ForeignKey('comhealth_test_groups.id'))
    group = db.relationship('ComHealthTestGroup', backref=db.backref('test_items'))

    price = db.Column('price', db.Numeric())
    receipts = association_proxy('invoices', 'receipt')


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

    @property
    def next(self):
        return u'{}{}{:06}'.format(self.code,str(self.buddhist_year)[-2:], self.count+1)


class ComHealthReceipt(db.Model):
    __tablename__ = 'comhealth_test_receipts'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    copy_number = db.Column('copy_number', db.Integer, default=1)
    created_datetime = db.Column('checkin_datetime', db.DateTime(timezone=True))
    record_id = db.Column('record_id', db.ForeignKey('comhealth_test_records.id'))
    record = db.relationship('ComHealthRecord',
                              backref=db.backref('receipts'))
    tests = association_proxy('invoices', 'test_item')
    comment = db.Column('comment', db.Text())
    paid = db.Column('paid', db.Boolean(), default=False)
    cancelled = db.Column('cancelled', db.Boolean(), default=False)
    cancel_comment = db.Column('cancel_comment', db.Text())
    issuer_id = db.Column('issuer_id', db.ForeignKey('comhealth_cashier.id'))
    issuer = db.relationship('ComHealthCashier',
                             foreign_keys=[issuer_id],
                             backref=db.backref('issued_receipts'))
    cashier_id = db.Column('cashier_id', db.ForeignKey('comhealth_cashier.id'))
    cashier = db.relationship('ComHealthCashier', foreign_keys=[cashier_id])
    payment_method = db.Column('payment_method', db.String(64))
    card_number = db.Column('card_number', db.String(16))
    print_profile_note = db.Column('print_profile_note', db.Boolean(), default=False)


class ComHealthReferenceTestProfile(db.Model):
    """All tests in the profile are reimbursable by the government.
    """
    __tablename__ = 'comhealth_reference_test_profile'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    profile_id = db.Column('profile_id', db.ForeignKey('comhealth_test_profiles.id'))
    profile = db.relationship('ComHealthTestProfile')


class ComHealthCustomerInfoSchema(ma.ModelSchema):
    class Meta:
        model = ComHealthCustomerInfo


class ComHealthCustomerSchema(ma.ModelSchema):
    info = fields.Nested(ComHealthCustomerInfoSchema)
    class Meta:
        model = ComHealthCustomer


class ComHealthRecordSchema(ma.ModelSchema):
    customer = fields.Nested(ComHealthCustomerSchema)
    class Meta:
        model = ComHealthRecord


class ComHealthServiceSchema(ma.ModelSchema):
    records = fields.Nested(ComHealthRecordSchema, many=True)
    class Meta:
        model = ComHealthService


class ComHealthTestProfileSchema(ma.ModelSchema):
    quote = fields.String()
    class Meta:
        model = ComHealthTestProfile


class ComHealthTestGroupSchema(ma.ModelSchema):
    class Meta:
        model = ComHealthTestGroup


class ComHealthTestSchema(ma.ModelSchema):
    default_price = fields.String()
    class Meta:
        model = ComHealthTest


class ComHealthOrgSchema(ma.ModelSchema):
    class Meta:
        model = ComHealthOrg