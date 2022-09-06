# -*- coding:utf-8 -*-
from sqlalchemy import Table

from app.main import db, ma
from sqlalchemy.sql import func
from ..asset.models import AssetItem


class RoomType(db.Model):
    __tablename__ = 'scheduler_room_types'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    type = db.Column('type', db.String(length=32))
    rooms = db.relationship('RoomResource', backref='type')

    def __repr__(self):
        return self.type


class RoomAvailability(db.Model):
    __tablename__ = 'scheduler_room_avails'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    availability = db.Column('availability', db.String(length=32))
    rooms = db.relationship('RoomResource', backref='availability')

    def __repr__(self):
        return self.availability


class RoomResource(db.Model):
    __tablename__ = 'scheduler_room_resources'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    location = db.Column('location', db.String(length=16))
    number = db.Column('number', db.String(16))
    floor = db.Column('floor', db.String())
    occupancy = db.Column('occupancy', db.Integer(), nullable=False)
    desc = db.Column('desc', db.Text())
    business_hour_start = db.Column('business_hour_start', db.Time())
    business_hour_end = db.Column('business_hour_end', db.Time())
    availability_id = db.Column('availability_id',
                                db.ForeignKey('scheduler_room_avails.id'))
    type_id = db.Column('type_id', db.ForeignKey('scheduler_room_types.id'))
    reservations = db.relationship('RoomEvent', backref='room')
    equipments = db.relationship(AssetItem, backref=db.backref('room'))

    def __str__(self):
        return u'Room: {} {}'.format(self.number, self.location)

    def __repr__(self):
        return u'Room: {}, ID: {}'.format(self.number, self.id)


class EventCategory(db.Model):
    __tablename__ = 'scheduler_event_categories'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    category = db.Column('category', db.String(255))

    def __str__(self):
        return u'{}'.format(self.category)


class RoomEvent(db.Model):
    __tablename__ = 'scheduler_room_reservations'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    room_id = db.Column('room_id', db.ForeignKey('scheduler_room_resources.id'),
                        nullable=False)
    category_id = db.Column('category_id',
                            db.ForeignKey('scheduler_event_categories.id'))
    category = db.relationship('EventCategory', backref=db.backref('events'))
    title = db.Column('title', db.String(255), nullable=False)
    start = db.Column('start', db.DateTime(timezone=True), nullable=False)
    end = db.Column('end', db.DateTime(timezone=True), nullable=False)
    iocode_id = db.Column('iocode_id', db.ForeignKey('iocodes.id'))
    occupancy = db.Column('occupancy', db.Integer())
    # number of sets of food/refreshment requested
    refreshment = db.Column('refreshment', db.Integer(), default=0)
    request = db.Column('request', db.Text())  # comma separated list of things
    approved = db.Column('approved', db.Boolean(), default=True)
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), server_default=None)
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True), server_default=None)
    cancelled_by = db.Column('cancelled_by', db.ForeignKey('staff_account.id'))
    approved_by = db.Column('approved_by', db.ForeignKey('staff_account.id'))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True), server_default=None)
    extra_items = db.Column('extra_items', db.JSON)
    note = db.Column('note', db.Text())
    iocode = db.relationship('IOCode', backref=db.backref('events' , lazy='dynamic'))
    google_event_id = db.Column('google_event_id', db.String(64))
    google_calendar_id = db.Column('google_calendar_id', db.String(255))


complaint_topic_assoc = Table('room_complaint_topic_assoc',
                              db.Column('room_complaint_topic_id', db.ForeignKey('scheduler_room_complaint_topics.id')),
                              db.Column('room_complaint_id', db.ForeignKey('scheduler_room_complaints.id')),
                              )


class RoomComplaintTopic(db.Model):
    __tablename__ = 'scheduler_room_complaint_topics'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(), nullable=False)


class RoomComplaint(db.Model):
    __tablename__ = 'scheduler_room_complaints'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    room_id = db.Column('room_id', db.ForeignKey('scheduler_room_resources.id'), nullable=False)
    room = db.relationship(RoomResource, backref=db.backref('complaints'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    note = db.Column('note', db.Text())
    commenter = db.Column('commenter', db.String(), info={'label': u'โดย',
                                                          'choices': [(c, c) for c in [u'นักศึกษา', u'บุคลากร', u'อื่น ๆ']]})
    topics = db.relationship(RoomComplaintTopic,
                             backref=db.backref('complaints'),
                             secondary=complaint_topic_assoc)
