# -*- coding:utf-8 -*-

from app.main import db
from app.models import Mission
from sqlalchemy.sql import func


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
