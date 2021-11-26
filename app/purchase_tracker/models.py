# -*- coding:utf-8 -*-
from app.main import db
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


class PurchaseTrackerAccount(db.Model):
    __tablename__ = 'tracker_accounts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(255), nullable=False, info={'label': u"ชื่อเรื่อง"})
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
    status = db.Column('status', db.String(), info={'label': u'สถานะ', 'choices': [(c, c) for c in [u'รออนุมัติ', u'รับเรื่อง']]})
    creation_date = db.Column('creation_date', db.DateTime(timezone=True), nullable=False)
    status_date = db.Column('status_date', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    comment = db.Column('comment', db.String())

    def __str__(self):
        return self.status





