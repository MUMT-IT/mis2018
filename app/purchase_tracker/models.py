# -*- coding:utf-8 -*-
from app.main import db
from app.staff.models import StaffAccount


class PurchaseTrackerAccount(db.Model):
    __tablename__ = 'tracker_accounts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(255), nullable=False, info={'label': u"ชื่อเรื่อง"})
    section = db.Column(db.String(255), nullable=False, info={'label': u"หัวข้อ"})
    number = db.Column(db.String(255), nullable=False, info={'label': u"เลขที่"})
    creation_date = db.Column('creation_date', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    desc = db.Column('desc', db.Text(), info={'label': u"รายละเอียด"})
    comment = db.Column('comment', db.Text(), info={'label': u"หมายเหตุ"})


    def __str__(self):
        return u'{}: {}'.format(self.subject, self.number)


class PurchaseTrackerStatus(db.Model):
    __tablename__ = 'tracker_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    status = db.Column('status', db.String(), info={'label': u'สถานะ', 'choices': [(c, c) for c in [u'รออนุมัติ', u'รับเรื่อง']]})
    creation_date = db.Column('creation_date', db.DateTime(timezone=True), nullable=False, info={'label': u"วันที่สร้าง"})
    status_date = db.Column('status_date', db.DateTime(timezone=True), nullable=False, info={'label': u"รายละเอียด"})
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    comment = db.Column('comment', db.Text(), info={'label': u"หมายเหตุ"})

    def __str__(self):
        return self.status


class PurchaseTrackerContact(db.Model):
    __tablename__ = 'tracker_contacts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, info={'label': u"ชื่อ"})
    age = db.Column(db.Integer, index=True, info={'label': u"อายุ"})
    address = db.Column(db.String(256), info={'label': u"ที่อยู่"})
    phone = db.Column(db.String(20), info={'label': u"เบอร์โทรศัพท์"})
    email = db.Column(db.String(120), info={'label': u"อีเมล"})

    def to_dict(self):
        return {
            'name': self.name,
            'age': self.age,
            'address': self.address,
            'phone': self.phone,
            'email': self.email
        }



