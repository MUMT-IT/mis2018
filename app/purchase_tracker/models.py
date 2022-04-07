# -*- coding:utf-8 -*-
from datetime import timedelta
from sqlalchemy import and_
from app.main import db
from app.models import Holidays
from app.staff.models import StaffAccount
from sqlalchemy import Date
from sqlalchemy import cast


class PurchaseTrackerAccount(db.Model):
    __tablename__ = 'tracker_accounts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(255), nullable=False, info={'label': u'ชื่อเรื่อง'})
    number = db.Column(db.String(255), nullable=False, info={'label': u'เลขที่หนังสือ'})
    booking_date = db.Column('booking_date', db.Date(), nullable=False, info={'label': u'วันที่หนังสือ'})
    amount = db.Column('amount', db.Float(), info={'label': u'วงเงินหลักการ'})
    formats = db.Column('formats', db.String(255), info={'label': u'รูปแบบหลักการ'})
    creation_date = db.Column('creation_datetime', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount)
    desc = db.Column('desc', db.Text(), info={'label': u'รายละเอียด'})
    comment = db.Column('comment', db.Text(), info={'label': u'หมายเหตุ'})
    url = db.Column(db.String(255), nullable=True)
    cancelled_datetime = db.Column('cancelled_datetime', db.DateTime(timezone=True), nullable=True)
    end_datetime = db.Column('end_datetime', db.DateTime(timezone=True), nullable=True,
                             info={'label': u'วันที่สิ้นสุด'})

    def __str__(self):
        return u'{}: {}'.format(self.subject, self.number, self.account_status)

    @property
    def weekdays(self):
        return sum([status.weekdays for status in self.records.all()])

    @staticmethod
    def count_weekdays(start_date, end_date):
        delta = end_date - start_date
        n = 0
        weekdays = 0
        while n <= delta.days:
            d = start_date + timedelta(n)
            if d.weekday() < 5:
                # if holidays and d not in holidays:
                weekdays += 1
            n += 1
        holidays = Holidays.query.filter(and_(cast(Holidays.holiday_date, Date) >= start_date,
                                              cast(Holidays.holiday_date, Date) <= end_date)).all()
        return weekdays - len(holidays)

    @property
    def total_weekdays(self):
        start_dates = []
        end_dates = []
        for record in self.records.all():
            start_dates.append(record.start_date)
            end_dates.append(record.end_date)
        if start_dates:
            first_start_date = sorted(start_dates)[0]
            last_end_date = sorted(end_dates)[-1]
        else:
            return 0
        return PurchaseTrackerAccount.count_weekdays(first_start_date, last_end_date)


class PurchaseTrackerStatus(db.Model):
    __tablename__ = 'tracker_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column('account_id', db.ForeignKey('tracker_accounts.id'))
    account = db.relationship('PurchaseTrackerAccount', backref=db.backref('records',
                                                                           lazy='dynamic',
                                                                           order_by='PurchaseTrackerStatus.start_date'))
    status = db.Column('status', db.String(), info={'label': u'สถานะ',
                                                    'choices': [(c, c) for c in
                                                                [u'กำลังดำเนินการ', u'ดำเนินการเสร็จสิ้น', u'ยกเลิก']]})
    creation_date = db.Column('creation_date', db.DateTime(timezone=True), nullable=False,
                              info={'label': u'วันที่สร้าง'})
    status_date = db.Column('status_date', db.DateTime(timezone=True), nullable=False, info={'label': u'วันที่สถานะ'})
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount)
    comment = db.Column('comment', db.Text(), info={'label': u'หมายเหตุ'})
    start_date = db.Column('start_date', db.Date(), nullable=False, info={'label': u'วันที่เริ่มต้น'})
    end_date = db.Column('end_date', db.Date(), nullable=False, info={'label': u'วันที่สิ้นสุด'})
    update_datetime = db.Column('update_date', db.DateTime(timezone=True), info={'label': u'วันที่แก้ไข'})
    activity = db.relationship('PurchaseTrackerActivity')
    activity_id = db.Column('activity_id', db.ForeignKey('tracker_activities.id'))
    other_activity = db.Column('other_activity', db.String(), info={'label': u'กิจกรรมอื่นๆ'})

    def __str__(self):
        return u'{}:{}'.format(self.status, self.activity)

    def to_list(self):
        delta = self.end_date - self.start_date
        duration = delta.days
        return [str(self.id),
                self.other_activity or self.activity.activity,
                self.start_date.isoformat(),
                self.end_date.isoformat(),
                duration,
                100,
                "",
                ]

    @property
    def weekdays(self):
        delta = self.end_date - self.start_date
        n = 0
        weekdays = 0
        while n <= delta.days:
            d = self.start_date + timedelta(n)
            if d.weekday() < 5:
                # if holidays and d not in holidays:
                weekdays += 1
            n += 1
        holidays = Holidays.query.filter(and_(cast(Holidays.holiday_date, Date) >= self.start_date,
                                              cast(Holidays.holiday_date, Date) <= self.end_date)).all()
        return weekdays - len(holidays)

    @property
    def total_days(self):
        delta = self.end_date - self.start_date
        return delta.days


class PurchaseTrackerActivity(db.Model):
    __tablename__ = 'tracker_activities'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    activity = db.Column('activity', db.String(255), nullable=False, info={'label': u'กิจกรรม'})

    def __str__(self):
        return u'{}'.format(self.activity)