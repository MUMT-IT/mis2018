from app.main import db, ma
from sqlalchemy.sql import func
from app.asset.models import AssetItem
from app.eduqa.models import EduQACourseSession
from sqlalchemy_utils import DateTimeRangeType

event_participant_assoc = db.Table('event_participant_assoc',
                                   db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id')),
                                   db.Column('event_id', db.Integer, db.ForeignKey('scheduler_room_reservations.id'))
                                   )

room_coordinator_assoc = db.Table('room_coordinator_assoc',
                                  db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id')),
                                  db.Column('room_id', db.Integer, db.ForeignKey('scheduler_room_resources.id'))
                                  )


class RoomType(db.Model):
    __tablename__ = 'scheduler_room_types'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    type = db.Column('type', db.String(length=32))
    rooms = db.relationship('RoomResource', backref='type')
    color = db.Column('color', db.String())

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
    equipments = db.relationship(AssetItem, backref=db.backref('room'))
    coordinator_id = db.Column('coordinator_id', db.ForeignKey('staff_account.id'))
    coordinator = db.relationship('StaffAccount')
    coordinators = db.relationship('StaffAccount',
                                   backref=db.backref('rooms'),
                                   secondary=room_coordinator_assoc)

    def __str__(self):
        if self.desc:
            return u'{} {} ({})'.format(self.number, self.location, self.desc)
        else:
            return u'{} {}'.format(self.number, self.location)

    def __repr__(self):
        return u'{}, ID: {}'.format(self.number, self.id)


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
    room = db.relationship(RoomResource, backref=db.backref('reservations',
                                                            lazy='dynamic',
                                                            cascade='all, delete-orphan'))
    category_id = db.Column('category_id',
                            db.ForeignKey('scheduler_event_categories.id'))
    category = db.relationship('EventCategory', backref=db.backref('events'))
    title = db.Column('title', db.String(255), nullable=False)
    start = db.Column('start', db.DateTime(timezone=True), nullable=False)
    end = db.Column('end', db.DateTime(timezone=True), nullable=False)
    datetime = db.Column(DateTimeRangeType())
    iocode_id = db.Column('iocode_id', db.ForeignKey('iocodes.id'))
    occupancy = db.Column('occupancy', db.Integer())
    # number of sets of food/refreshment requested
    refreshment = db.Column('refreshment', db.Integer(), default=0)
    request = db.Column('request', db.Text(), info={'label': 'ความต้องการเพิ่มเติม'})  # comma separated list of things
    approved = db.Column('approved', db.Boolean(), default=True)
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    creator = db.relationship('StaffAccount', foreign_keys=[created_by])
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), server_default=None)
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True), server_default=None)
    cancelled_by = db.Column('cancelled_by', db.ForeignKey('staff_account.id'))
    approved_by = db.Column('approved_by', db.ForeignKey('staff_account.id'))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True), server_default=None)
    extra_items = db.Column('extra_items', db.JSON)
    note = db.Column('note', db.Text())
    iocode = db.relationship('IOCode', backref=db.backref('events', lazy='dynamic'))
    google_event_id = db.Column('google_event_id', db.String(64))
    google_calendar_id = db.Column('google_calendar_id', db.String(255))
    participants = db.relationship('StaffAccount', secondary=event_participant_assoc,
                                   backref=db.backref('events', lazy='dynamic'))
    notify_participants = db.Column('notify_participants', db.Boolean(), default=True)
    course_session_id = db.Column('course_session_id', db.ForeignKey('eduqa_course_sessions.id'))
    course_session = db.relationship(EduQACourseSession, backref=db.backref('events', cascade='all, delete-orphan'))
    meeting_event_id = db.Column('meeting_event_id', db.ForeignKey('meeting_events.id'))

    def to_dict(self):
        return {
            'room_number': self.room.number,
            'room_location': self.room.location,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'start': self.start.isoformat(),
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'end': self.end.isoformat(),
            'creator': self.creator.fullname if self.creator else None,
            'category': self.category.category if self.category else None,
            'note': self.note
        }

    def __str__(self):
        return f'{self.room.number}[ID={self.room.id}]: {self.start.isoformat()}-{self.end.isoformat()}'
