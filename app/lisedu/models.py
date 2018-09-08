from flask_login import UserMixin
from sqlalchemy.sql import func
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
