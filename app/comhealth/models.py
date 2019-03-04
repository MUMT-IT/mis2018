from ..main import db

test_profile_assoc_table = db.Table('comhealth_test_profile_assoc',
    db.Column('test_id', db.Integer, db.ForeignKey('comhealth_tests.id'), primary_key=True),
    db.Column('profile_id', db.Integer, db.ForeignKey('comhealth_test_profiles.id'), primary_key=True)
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


class ComHealthTest(db.Model):
    __tablename__ = 'comhealth_tests'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())
    # price = db.Column('price', db.Numeric(), default=0)

    def __str__(self):
        return self.name


class ComHealthTestProfile(db.Model):
    __tablename__ = 'comhealth_test_profiles'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(64), index=True)
    desc = db.Column('desc', db.Text())
    tests = db.relationship('ComHealthTest', secondary=test_profile_assoc_table,
                            backref=db.backref('profiles', lazy=True))

    def __str__(self):
        return self.name


class ComHealthRecord(db.Model):
    __tablename__ = 'comhealth_test_records'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    date = db.Column('date', db.Date())
    labno = db.Column('labno', db.Integer)
    customer_id = db.Column('customer_id', db.ForeignKey('comhealth_customers.id'))
    customer = db.relationship('ComHealthCustomer', backref=db.backref('records'))
    service_id = db.Column('service_id', db.ForeignKey('comhealth_services.id'))
    service = db.relationship('ComHealthService',
                              backref=db.backref('records'))


class ComHealthTestItem(db.Model):
    __tablename__ = 'comhealth_test_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    record_id = db.Column('record_id', db.ForeignKey('comhealth_test_records.id'))
    test_id = db.Column('test_id', db.ForeignKey('comhealth_tests.id'))
    test = db.relationship('ComHealthTest')
    record = db.relationship('ComHealthRecord',
                             backref=db.backref('test_items'),)


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

    def __str__(self):
        return str(self.date)
