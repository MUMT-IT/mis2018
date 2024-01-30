# -*- coding:utf-8 -*-
from sqlalchemy import func
from app.eduqa.models import EduQAStudent
from app.main import db
from app.staff.models import StaffAccount


class AVUBorrowReturnServiceDetail(db.Model):
    __tablename__ = 'avu_borrow_return_service_details'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    number = db.Column('number', db.String(), info={'label': u'เลขที่'})
    type_requester = db.Column('type_requester', db.String(), info={'label': u'ประเภทผู้ใช้บริการ',
                                                                                    'choices': [(None,
                                                                                                 u'--โปรดเลือก--'),
                                                                                                ('Lecturer', 'Lecturer'),
                                                                                                ('Staff', 'Staff'),
                                                                                                ('Student', 'Student')
                                                                                                ]})
    objective = db.Column('objective', db.Text(), info={'label': u'วัตถุประสงค์ในการใช้บริการ'})
    request_date = db.Column('request_date', db.DateTime(timezone=True), info={'label': u'วัน-เวลายืม'})
    created_at = db.Column('created_at', db.Date(), server_default=func.now())
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, foreign_keys=[staff_id])
    student_year = db.Column(db.String(), info={'label': 'ระดับ',
                                                'choices': [(c, c) for c in ('ปี 1', 'ปี 2', 'ปี 3', 'ปี 4')]})
    student_id = db.Column(db.Integer, db.ForeignKey('eduqa_students.id'))
    student = db.relationship(EduQAStudent,
                              backref=db.backref('borrow_return_service_records', cascade='all, delete-orphan'))
    procurement_id = db.Column('procurement_id', db.ForeignKey('procurement_details.id'))
    procurement = db.relationship('ProcurementDetail',
                           backref=db.backref('lender_services', lazy='dynamic'))
    lending_date = db.Column('lending_date', db.DateTime(timezone=True), info={'label': u'วัน-เวลาให้ยืม'})
    received_date = db.Column('received_date', db.DateTime(timezone=True), info={'label': u'วัน-เวลาคืน'})