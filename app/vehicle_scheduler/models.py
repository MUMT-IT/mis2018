# -*- coding:utf-8 -*-

import pytz

from app.main import db, ma
from sqlalchemy.sql import func

tz = pytz.timezone('Asia/Bangkok')


class VehicleType(db.Model):
    __tablename__ = 'scheduler_vehicle_types'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    type = db.Column('type', db.String(length=32))
    vehicles = db.relationship('VehicleResource', backref='type')

    def __repr__(self):
        return self.type


class VehicleAvailability(db.Model):
    __tablename__ = 'scheduler_vehicle_avails'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    availability = db.Column('availability', db.String(length=32))
    vehicles = db.relationship('VehicleResource', backref='availability')

    def __repr__(self):
        return self.availability


class VehicleResource(db.Model):
    __tablename__ = 'scheduler_vehicle_resources'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    license = db.Column('license', db.String(8), nullable=False)
    maker = db.Column('maker', db.String(16), nullable=False)
    model = db.Column('model', db.String(16))
    year = db.Column('year', db.String(4))
    occupancy = db.Column('occupancy', db.Integer(), nullable=False)
    desc = db.Column('desc', db.Text())
    business_hour_start = db.Column('business_hour_start', db.Time())
    business_hour_end = db.Column('business_hour_end', db.Time())
    availability_id = db.Column('availability_id',
                                db.ForeignKey('scheduler_vehicle_avails.id'))
    type_id = db.Column('type_id', db.ForeignKey('scheduler_vehicle_types.id'))
    # reservations = db.relationship('RoomEvent', backref='room')


class VehicleBooking(db.Model):
    __tablename__ = 'scheduler_vehicle_bookings'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    vehicle_id = db.Column('vehicle_id',
                        db.ForeignKey('scheduler_vehicle_resources.id'),
                        nullable=False)
    vehicle = db.relationship('VehicleResource', backref=db.backref('bookings'))
    title = db.Column('title', db.String(255), nullable=False, info={'label': u'กิจกรรม'})
    init_milage = db.Column('init_milage', db.Integer, nullable=True, info={'label': u'เลขไมล์เริ่มต้น'})
    end_milage = db.Column('end_milage', db.Integer, nullable=True, info={'label': u'เลขไมล์สิ้นสุด'})
    toll_fee = db.Column('toll_fee', db.Float(), default=0.0, info={'label': u'ค่าทางด่วน'})
    distance = db.Column('distance', db.Integer, nullable=True, info={'label': u'ระยะทาง'})
    init_location = db.Column('init_location', db.String(255), nullable=True, info={'label': u'สถานที่เริ่มต้น'})
    destination = db.Column('destination', db.String(255), nullable=True, info={'label': u'สถานที่สิ้นสุด'})
    # use TextInput for compatibility with the daterangepicker plugin
    start = db.Column('start', db.DateTime(timezone=True), nullable=False, info={'label': u'วันและเวลาเริ่มต้น'})
    end = db.Column('end', db.DateTime(timezone=True), nullable=False, info={'label': u'วันและเวลาสิ้นสุด'})
    iocode_id = db.Column('iocode_id', db.ForeignKey('iocodes.id'))
    iocode = db.relationship('IOCode', backref=db.backref('vehicle_bookings'))
    org_id = db.Column('org_id', db.ForeignKey('orgs.id'))
    org = db.relationship('Org', backref=db.backref('vehicle_bookings'))
    num_passengers = db.Column('num_passengers', db.Integer(), info={'min': 1, 'label': u'จำนวนผู้โดยสาร'})
    approved = db.Column('approved', db.Boolean(), default=False)
    closed = db.Column('closed', db.Boolean(), default=False)
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), server_onupdate=func.now())
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    cancelled_by = db.Column('cancelled_by', db.ForeignKey('staff_account.id'))
    approved_by = db.Column('approved_by', db.ForeignKey('staff_account.id'))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True), server_default=None)
    desc = db.Column('desc', db.Text(), info={'label': u'รายละเอียด'})
    google_event_id = db.Column('google_event_id', db.String(64))
    google_calendar_id = db.Column('google_calendar_id', db.String(255))

    def to_dict(self):
        return {'id': self.id,
                'license': self.vehicle.license,
                'org': self.org.name,
                'title': u'{}: {}'.format(self.vehicle.license, self.title),
                'description': self.desc,
                'start': self.start.astimezone(tz).isoformat(),
                'end': self.end.astimezone(tz).isoformat(),
                'resourceId': self.vehicle.id,
                'approved': self.approved,
                'borderColor': '',
                'backgroundColor': '',
                'textColor': '',
                'closed': self.closed,
                }
