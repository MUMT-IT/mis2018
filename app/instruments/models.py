# -*- coding:utf-8 -*-
from sqlalchemy import func
from app.main import db
import pytz

tz = pytz.timezone('Asia/Bangkok')


class InstrumentsBooking(db.Model):
    __tablename__ = 'instrument_bookings'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    detail_id = db.Column('detail_id', db.ForeignKey('procurement_details.id'))
    detail = db.relationship('ProcurementDetail', backref=db.backref('instruments_detail'))
    title = db.Column('title', db.String(), nullable=False, info={'label': u'กิจกรรม'})
    start = db.Column('start', db.DateTime(timezone=True), nullable=False, info={'label': u'วันและเวลาเริ่มต้น'})
    end = db.Column('end', db.DateTime(timezone=True), nullable=False, info={'label': u'วันและเวลาสิ้นสุด'})
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    creator = db.relationship('StaffAccount', foreign_keys=[created_by])
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), server_onupdate=func.now())
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    cancelled_by = db.Column('cancelled_by', db.ForeignKey('staff_account.id'))
    desc = db.Column('desc', db.Text(), info={'label': u'รายละเอียด'})

    def to_dict(self):
        return {'id': self.id,
                'title': u'{}'.format(self.title),
                'description': self.desc,
                'start': self.start.astimezone(tz).isoformat(),
                'end': self.end.astimezone(tz).isoformat(),
                'borderColor': '',
                'backgroundColor': '',
                'textColor': ''
                }

