from flask_login import UserMixin
from sqlalchemy.sql import func
from ..models import Student
from ..main import db


class StudentUser(UserMixin):
    def __init__(self, user):
        self.id = user.id
        self.account = user

    def get_id(self):
        return self.id


class StudentProfile(db.Model):
    __tablename__ = 'student_profile'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    updated_at = db.Column('updated_at', db.DateTime(), onupdate=func.now())
    gender = db.Column('gender', db.String(), nullable=True)
    dob = db.Column('dob', db.Date(), nullable=True)
    student_id = db.Column('student_id', db.ForeignKey('students.id'))
    cur_addr_id = db.Column('cur_addr', db.ForeignKey('addresses.id'))
    student = db.relationship(Student,
                    backref=db.backref('profile', uselist=False))

class TestGroup(db.Model):
    __tablename__ = 'lis_test_groups'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    abbr = db.Column('abbr', db.String(), nullable=False)
    name = db.Column('name', db.String(), nullable=False)
    description = db.Column('description', db.String(), nullable=True)


class Test(db.Model):
    __tablename__ = 'lis_tests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    abbr = db.Column('abbr', db.String(), nullable=False)
    name = db.Column('name', db.String(), nullable=False)
    description = db.Column('description', db.String(), nullable=True)
    cost = db.Column('cost', db.Numeric, nullable=True)
    quantitative = db.Column('quantitative', db.Boolean(), nullable=False)
    updated_at = db.Column('updated_at', db.DateTime(), onupdate=func.now())
    created_at = db.Column('created_at', db.DateTime(), default=func.now())
    unit = db.Column('unit', db.String(), nullable=True)
    group_id = db.Column('group_id', db.ForeignKey('lis_test_groups.id'))
    group = db.relationship(TestGroup, backref=db.backref('tests'))
    disabled = db.Column('status', db.Boolean(), default=False)


class Order(db.Model):
    __tablename__ = 'lis_orders'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    patient_id = db.Column('patient_id', db.ForeignKey('students.id'), nullable=False)
    patient = db.relationship(Student, backref=db.backref('lis_orders'),
                              foreign_keys=[patient_id])
    lab_no = db.Column('lab_no', db.String(), nullable=False)
    # creator
    created_at = db.Column('created_at', db.DateTime(), default=func.now())
    creator_id = db.Column('created_by', db.ForeignKey('students.id'))
    creator = db.relationship(Student, backref=db.backref('result_lists'),
                              foreign_keys=[creator_id])
    # test
    test_id = db.Column('test_id', db.ForeignKey('lis_tests.id'))
    test = db.relationship(Test, backref=db.backref('orders'))


class Result(db.Model):
    __tablename__ = 'lis_results'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    created_at = db.Column('created_at', db.DateTime(), default=func.now())
    reporter_id = db.Column('reported_by', db.ForeignKey('students.id'), nullable=False)
    reporter = db.relationship(Student, backref=db.backref('results'),
                               foreign_keys=[reporter_id])
    quant_value = db.Column('quant_value', db.Numeric(), nullable=True)
    qual_value = db.Column('qual_value', db.String(), nullable=True)
    revision = db.Column('revision', db.Integer(), nullable=False, default=0)
    # order
    order_id = db.Column('order_id', db.ForeignKey('lis_orders.id'))
    order = db.relationship(Order, backref=db.backref('results'))
    comment = db.Column('comment', db.String(), nullable=True)
    # commenter
    commenter_id = db.Column('commenter_id', db.ForeignKey('students.id'))
    commenter = db.relationship('Student', backref=db.backref('result_comments'),
                                foreign_keys=[commenter_id])
