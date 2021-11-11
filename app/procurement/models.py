# -*- coding:utf-8 -*-
from app.main import db
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


class ProcurementDetail(db.Model):
    __tablename__ = 'procurement_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    list = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(255), nullable=False)
    available = db.Column(db.String(255), nullable=False)
    category_id = db.Column('category_id', db.ForeignKey('procurement_categories.id'))
    category = db.relationship('ProcurementCategory',
                               backref=db.backref('items', lazy='dynamic'))
    model = db.Column('model', db.String())
    maker = db.Column('maker', db.String())
    size = db.Column('size', db.String())
    desc = db.Column('desc', db.String())
    comment = db.Column('comment', db.String())

    def __str__(self):
        return u'{}: {}'.format(self.list, self.code)


class ProcurementCategory(db.Model):
    __tablename__ = 'procurement_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(255), nullable=False)

    def __str__(self):
        return self.type


class ProcurementStatus(db.Model):
    __tablename__ = 'procurement_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    status = db.Column('status', db.String())

    def __str__(self):
        return self.status


class ProcurementRecord(db.Model):
    __tablename__ = 'procurement_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    location_id = db.Column('location_id',
                            db.ForeignKey('scheduler_room_resources.id'))
    item_id = db.Column('item_id', db.ForeignKey('procurement_details.id'))
    item = db.relationship('ProcurementDetail',
                           backref=db.backref('records', lazy='dynamic'))
    location = db.relationship(RoomResource,
                               backref=db.backref('items', lazy='dynamic'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    status_id = db.Column('status_id', db.ForeignKey('procurement_statuses.id'))
    status = db.relationship('ProcurementStatus',
                             backref=db.backref('records', lazy='dynamic'))




