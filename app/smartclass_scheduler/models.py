# -*- coding:utf-8 -*-
from app.main import db
from sqlalchemy.sql import func


class SmartClassResourceType(db.Model):
    __tablename__ = 'smartclass_scheduler_resource_types'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    resource_type = db.Column('type', db.String(length=32))

    def __repr__(self):
        return self.resource_type


class SmartClassOnlineAccount(db.Model):
    __tablename__ = 'smartclass_scheduler_online_accounts'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)
    resource_type_id = db.Column('resource_type_id',
                                 db.ForeignKey('smartclass_scheduler_resource_types.id'))
    resource_type = db.relationship(SmartClassResourceType,
                                    backref=db.backref('resources'))

    def __str__(self):
        return self.name


class SmartClassOnlineAccountEvent(db.Model):
    __tablename__ = 'smartclass_scheduler_online_account_events'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    account_id = db.Column('account_id',
                           db.ForeignKey('smartclass_scheduler_online_accounts.id'),
                           nullable=False)
    title = db.Column('title', db.String(255), nullable=False, info={'label': u'กิจกรรม'})
    start = db.Column('start', db.DateTime(timezone=True), nullable=False, info={'label': u'เริ่ม'})
    end = db.Column('end', db.DateTime(timezone=True), nullable=False, info={'label': u'สิ้นสุด'})
    occupancy = db.Column('occupancy', db.Integer(), info={'label': u'ผู้เข้าร่วม'})
    approved = db.Column('approved', db.Boolean(), default=True)
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), server_default=None)
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True), server_default=None)
    cancelled_by = db.Column('cancelled_by', db.ForeignKey('staff_account.id'))
    approved_by = db.Column('approved_by', db.ForeignKey('staff_account.id'))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True), server_default=None)
    note = db.Column('note', db.Text(), info={'label': u'หมายเหตุ'})
    account = db.relationship(SmartClassOnlineAccount, backref=db.backref('events'))

