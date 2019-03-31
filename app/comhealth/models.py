from ..main import db, ma
from marshmallow import fields


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


class ComHealthOrg(db.Model):
    __tablename__ = 'comhealth_orgs'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255), index=True)


class ComHealthCustomer(db.Model):
    __tablename__ = 'comhealth_customers'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    title = db.Column('title', db.String(32))
    firstname = db.Column('firstname', db.String(255), index=True)
    lastname = db.Column('lastname', db.String(255), index=True)
    org_id = db.Column('org_id', db.ForeignKey('comhealth_orgs.id'))
    org = db.relationship('ComHealthOrg', backref=db.backref('employees', lazy=True))
    dob = db.Column('dob', db.Date())
    gender = db.Column('gender', db.Integer)

    def __str__(self):
        return u'{}{} {} {}'.format(self.title, self.firstname,
                                    self.lastname, self.org.name)


class ComHealthContainer(db.Model):
    __tablename__ = 'comhealth_containers'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('code', db.String(64), index=True)
    detail = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())
    volume = db.Column('volume', db.Numeric(), default=0)


    def __str__(self):
        return self.name


class ComHealthTest(db.Model):
    __tablename__ = 'comhealth_tests'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(64), index=True)
    name = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())

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
    service = db.relationship('ComHealthService',
                              backref=db.backref('records'))
    checkin_datetime = db.Column('checkin_datetime', db.DateTime(timezone=True))
    ordered_tests = db.relationship('ComHealthTestItem', backref=db.backref('records'),
                                    secondary=test_item_record_table)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))


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


class ComHealthTestProfileItem(db.Model):
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
        return str(self.date)


class ComHealthCustomerSchema(ma.ModelSchema):
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
