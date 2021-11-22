# -*- coding:utf-8 -*-
from app.main import db
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


class PurchaseTrackerAccount(db.Model):
    __tablename__ = 'tracker_accounts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(255), nullable=False)
    section = db.Column(db.String(255), nullable=False)
    number = db.Column(db.String(255), nullable=False)
    creation_date = db.Column('creation_date', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    desc = db.Column('desc', db.String())
    comment = db.Column('comment', db.String())

    def __str__(self):
        return u'{}: {}'.format(self.subject, self.number)


class PurchaseTrackerStatus(db.Model):
    __tablename__ = 'tracker_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    status = db.Column('status', db.String())

    def __str__(self):
        return self.status


class PurchaseTrackerRecord(db.Model):
    __tablename__ = 'tracker_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    #location_id = db.Column('location_id',
                            #db.ForeignKey('scheduler_room_resources.id'))
    #location = db.relationship(RoomResource,
                               #backref=db.backref('items', lazy='dynamic'))
    order_id = db.Column('order_id', db.ForeignKey('tracker_accounts.id'))
    order = db.relationship('PurchaseTrackerAccount',
                           backref=db.backref('records', lazy='dynamic'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    status_id = db.Column('status_id', db.ForeignKey('tracker_statuses.id'))
    status = db.relationship('PurchaseTrackerStatus',
                             backref=db.backref('records', lazy='dynamic'))




