# -*- coding:utf-8 -*-
from app.main import db
from app.staff.models import StaffAccount


class PurchaseTrackerAccount(db.Model):
    __tablename__ = 'tracker_accounts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(255), nullable=False, info={'label': u"ชื่อเรื่อง"})
    number = db.Column(db.String(255), nullable=False, info={'label': u"เลขที่"})
    creation_date = db.Column('creation_datetime', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount)
    desc = db.Column('desc', db.Text(), info={'label': u"รายละเอียด"})
    comment = db.Column('comment', db.Text(), info={'label': u"หมายเหตุ"})
    url = db.Column(db.String(255), nullable=True)
    account_status = db.Column(db.String(255),
                               info={'label': u'สถานะ', 'choices': [(c, c) for c in [u'สิ้นสุด', u'ยกเลิก']]})
    end_datetime = db.Column('end_datetime', db.DateTime(timezone=True), nullable=True,
                             info={'label': u'วันที่สิ้นสุด'})

    def __str__(self):
        return u'{}: {}'.format(self.subject, self.number)


class PurchaseTrackerStatus(db.Model):
    __tablename__ = 'tracker_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column('account_id', db.ForeignKey('tracker_accounts.id'))
    account = db.relationship('PurchaseTrackerAccount', backref=db.backref('records', lazy='dynamic'))
    status = db.Column('status', db.String(), info={'label': u'สถานะ',
                                                    'choices': [(c, c) for c in
                                                                [u'กำลังดำเนินการ', u'ดำเนินการเสร็จสิ้น', u'ยกเลิก']]})
    creation_date = db.Column('creation_date', db.DateTime(timezone=True), nullable=False,
                              info={'label': u"วันที่สร้าง"})
    status_date = db.Column('status_date', db.DateTime(timezone=True), nullable=False, info={'label': u"วันที่สถานะ"})
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount)
    comment = db.Column('comment', db.Text(), info={'label': u"หมายเหตุ"})
    start_date = db.Column('start_date', db.Date(), nullable=False, info={'label': u'วันที่เริ่มต้น'})
    end_date = db.Column('end_date', db.Date(), nullable=False, info={'label': u'วันที่สิ้นสุด'})
    update_datetime = db.Column('update_date', db.DateTime(timezone=True), info={'label': u'วันที่แก้ไข'})
    activity = db.Column('activity', db.String(255), nullable=False, info={'label': u'กิจกรรม'})


    def __str__(self):
        return u'{}:{}'.format(self.status, self.activity)
