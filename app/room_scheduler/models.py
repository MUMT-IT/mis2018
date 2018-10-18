from app.main import db, ma
from sqlalchemy.sql import func


class RoomType(db.Model):
    __tablename__ = 'scheduler_room_types'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    type = db.Column('type', db.String(length=32))
    rooms = db.relationship('RoomResource', backref='type')


class RoomAvailability(db.Model):
    __tablename__ = 'scheduler_room_avails'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    availability = db.Column('availability', db.String(length=32))
    rooms = db.relationship('RoomResource', backref='availability')


class RoomResource(db.Model):
    __tablename__ = 'scheduler_room_resources'
    id = db.Column('id', db.Integer(), primary_key=True,
                    autoincrement=True)
    location = db.Column('location', db.String(length=16))
    number = db.Column('number', db.String(16))
    occupancy = db.Column('occupancy', db.Integer(), nullable=False)
    desc = db.Column('desc', db.Text())
    business_hour_start = db.Column('business_hour_start', db.Time())
    business_hour_end = db.Column('business_hour_end', db.Time())
    availability_id = db.Column('availability_id',
                                db.ForeignKey('scheduler_room_avails.id'))
    type_id = db.Column('type_id', db.ForeignKey('scheduler_room_types.id'))
    reservations = db.relationship('RoomEvent', backref='room')


class RoomEvent(db.Model):
    __tablename__ = 'scheduler_room_reservations'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    room_id = db.Column('room_id', db.ForeignKey('scheduler_room_resources.id'),
                        nullable=False)
    title = db.Column('title', db.String(255), nullable=False)
    start = db.Column('start', db.DateTime(), nullable=False)
    end = db.Column('end', db.DateTime(), nullable=False)
    occupancy = db.Column('occupancy', db.Integer())
    refreshment = db.Column('refreshment', db.Integer(), default=0)
    request = db.Column('request', db.Text())
    approved = db.Column('approved', db.Boolean(), default=True)
    required_permission = db.Column('required_permission', db.Boolean(), default=False)
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    approved_by = db.Column('approved_by', db.ForeignKey('staff_account.id'))
