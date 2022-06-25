# -*- coding:utf-8 -*-
from sqlalchemy import func
from wtforms.validators import Email

from app.main import db
from app.models import StaffAccount, Dataset, CoreService


pdpa_request_datasets = db.Table('pdpa_request_datasets',
                        db.Column('dataset_id', db.Integer, db.ForeignKey('db_datasets.id'), primary_key=True),
                        db.Column('pdpa_request_id', db.Integer, db.ForeignKey('pdpa_requests.id'), primary_key=True)
                        )


class PDPARequestType(db.Model):
    __tablename__ = 'pdpa_types'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)


class PDPARequest(db.Model):
    __tablename__ = 'pdpa_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    service_id = db.Column('service_id', db.ForeignKey('db_core_services.id'))
    request_type_id = db.Column('request_type_id', db.ForeignKey('pdpa_types.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    requester_name = db.Column('requester_name', db.String(), nullable=False, info={'label': u'ชื่อ นามสกุล'})
    requester_email = db.Column('requester_email', db.String(), info={'label': u'อีเมล', 'validators': Email()})
    requester_phone = db.Column('requester_phone', db.String(), info={'label': u'โทรศัพท์'})
    received_at = db.Column('received_at', db.DateTime(timezone=True))
    receiver_id = db.Column('received_by', db.ForeignKey('staff_account.id'))
    detail = db.Column('detail', db.Text(), info={'label': u'รายละเอียดเพิ่มเติม'})
    decided_at = db.Column('approved_at', db.DateTime(timezone=True))
    decision = db.Column('decision', db.String(), info={'label': u'ผลการตัดสิน',
                                                        'choices': [(c, c) for c in [u'approved', u'rejected']]})
    priority = db.Column('priority', db.Integer(), info={'label': u'ระดับ',
                                                         'choices': [(c,f) for c,f in ((1, u'ระดับต้น'),
                                                                                       (2, u'ระดับกลาง'),
                                                                                       (3, u'ระดับสูง'))]})
    service = db.relationship(CoreService, backref=db.backref('pdpa_requests',
                                                              lazy='dynamic',
                                                              cascade='all, delete-orphan'))
    request_type = db.relationship(PDPARequestType, backref=db.backref('requests',
                                                                       lazy='dynamic',
                                                                       cascade='all, delete-orphan'))
    datasets = db.relationship(Dataset, secondary=pdpa_request_datasets, lazy='subquery',
                               backref=db.backref('pdpa_requests', lazy=True))
