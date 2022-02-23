# -*- coding:utf-8 -*-

from app.main import db
from app.models import Mission, Org
from sqlalchemy.sql import func


data_service_assoc = db.Table('data_service_assoc',
    db.Column('data_id', db.Integer, db.ForeignKey('db_data.id'), primary_key=True),
    db.Column('core_service_id', db.Integer, db.ForeignKey('db_core_services.id'), primary_key=True)
)


data_process_assoc = db.Table('data_process_assoc',
    db.Column('data_id', db.Integer, db.ForeignKey('db_data.id'), primary_key=True),
    db.Column('process_id', db.Integer, db.ForeignKey('db_processes.id'), primary_key=True),
)


class CoreService(db.Model):
    __tablename__ =  'db_core_services'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    service = db.Column('service', db.String(255), nullable=False, info={'label': u'บริการ'})
    mission_id = db.Column('mission_id', db.ForeignKey('missions.id'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now)
    mission = db.relationship(Mission, backref=db.backref('services', lazy='dynamic',
                                                            cascade='all, delete-orphan'))
    data = db.relationship('Data', secondary=data_service_assoc, lazy='subquery',
                                        backref=db.backref('core_services', lazy=True))


class Data(db.Model):
    __tablename__ =  'db_data'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255), nullable=False, info={'label': u'ข้อมูล'})
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now)
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))


class Process(db.Model):
    __tablename__ =  'db_processes'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    category = db.Column('category', db.String(), nullable=False,
            info={'label': u'กลุ่มงาน', 'choices': [(c,c) for c in ['back_office', 'regulation',
                                                                    'performance', 'crm']]})
    name = db.Column('name', db.String(255), nullable=False, info={'label': u'กระบวนการ'})
    org_id = db.Column('org_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('processes', lazy=True))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now)
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    data = db.relationship(Data, secondary=data_process_assoc, lazy='subquery',
                                        backref=db.backref('processes', lazy=True))
