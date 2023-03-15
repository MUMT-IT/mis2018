# -*- coding:utf-8 -*-
from app.main import db


class AlumniInformation(db.Model):
    __tablename__ = 'alumni_information'
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    student_id = db.Column('student_id', db.Integer(), info={'label': u'รหัสนักศึกษา'})
    th_title = db.Column('th_title', db.String(), info={'label': u'คำนำหน้า'})
    th_firstname = db.Column('th_firstname', db.String(), nullable=True, info={'label': u'ชื่อ'})
    th_lastname = db.Column('th_lastname', db.String(), nullable=True, info={'label': u'นามสกุล'})
    contact = db.Column('contact', db.String(), info={'label': u'ช่องทางการติดต่อ'})
    occupation = db.Column('occupation', db.String(), info={'label': u'อาชีพ'})
    workplace = db.Column('workplace', db.String(), info={'label': u'สถานที่ทำงาน'})
    province = db.Column('province', db.String(), info={'label': u'จังหวัดที่ทำงาน'})