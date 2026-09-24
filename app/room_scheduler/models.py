from app.main import db, ma
from sqlalchemy.sql import func
from app.asset.models import AssetItem
from sqlalchemy_utils import DateTimeRangeType

event_participant_assoc = db.Table('event_participant_assoc',
                                   db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id')),
                                   db.Column('event_id', db.Integer, db.ForeignKey('scheduler_room_reservations.id'))
                                   )

room_coordinator_assoc = db.Table('room_coordinator_assoc',
                                  db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id')),
                                  db.Column('room_id', db.Integer, db.ForeignKey('scheduler_room_resources.id'))
                                  )

room_conjoined_assoc = db.Table(
    'scheduler_room_conjoined_rooms',
    db.Column('room_id', db.Integer,
              db.ForeignKey('scheduler_room_resources.id', ondelete='CASCADE'),
              primary_key=True),
    db.Column('conjoined_room_id', db.Integer,
              db.ForeignKey('scheduler_room_resources.id', ondelete='CASCADE'),
              primary_key=True),
    db.CheckConstraint('room_id <> conjoined_room_id', name='ck_conjoined_rooms_distinct'),
)

room_event_room_assoc = db.Table(
    'scheduler_room_reservation_rooms',
    db.Column('event_id', db.Integer,
              db.ForeignKey('scheduler_room_reservations.id', ondelete='CASCADE'),
              primary_key=True),
    db.Column('room_id', db.Integer,
              db.ForeignKey('scheduler_room_resources.id', ondelete='CASCADE'),
              primary_key=True),
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
    conjoined_rooms_forward = db.relationship(
        'RoomResource',
        secondary=room_conjoined_assoc,
        primaryjoin=id == room_conjoined_assoc.c.room_id,
        secondaryjoin=id == room_conjoined_assoc.c.conjoined_room_id,
        backref=db.backref('conjoined_rooms_reverse'),
    )

    @property
    def conjoined_rooms(self):
        """Return both sides of the undirected conjoined-room relationship."""
        rooms = list(self.conjoined_rooms_forward) + list(self.conjoined_rooms_reverse)
        return sorted({room.id: room for room in rooms}.values(), key=lambda room: room.number or '')

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
    rooms = db.relationship(
        RoomResource,
        secondary=room_event_room_assoc,
        backref=db.backref('room_events', lazy='dynamic'),
    )
    category_id = db.Column('category_id',
                            db.ForeignKey('scheduler_event_categories.id'))
    category = db.relationship('EventCategory', backref=db.backref('events'))
    title = db.Column('title', db.String(255), nullable=False)
    start = db.Column('start', db.DateTime(timezone=True), nullable=False)
    end = db.Column('end', db.DateTime(timezone=True), nullable=False)
    repeat_end = db.Column('repeat_end', db.Date(), info={'label': 'จองซ้ำถึงวันที่'})
    datetime = db.Column(DateTimeRangeType())
    hour = db.Column('hour', db.String(), info={'label': 'จำนวนชั่วโมง', 'choices': [('', 'กรุณาเลือกจำนวนชั่วโมง'),
                                                                                     ('1', '1 ชั่วโมง'),
                                                                                     ('2', '2 ชั่วโมง'),
                                                                                     ('3', '3 ชั่วโมง'),
                                                                                     ('4', '4 ชั่วโมง'),
                                                                                     ('5', '5 ชั่วโมง'),
                                                                                     ('6', '6 ชั่วโมง'),
                                                                                     ('7', '7 ชั่วโมง'),
                                                                                     ('8', '8 ชั่วโมง'),
                                                                                     ('9', '9 ชั่วโมง'),
                                                                                     ('10', '10 ชั่วโมง')
                                                                                     ]
                                                })
    booking = db.Column('booking', db.String(), info={'label': 'รอบการจองซ้ำ', 'choices': [('', 'กรุณาเลือกรอบการจองซ้ำ'),
                                                                                        ('ทุกวัน (รวมเสาร์-อาทิตย์)',
                                                                                         'ทุกวัน (รวมเสาร์-อาทิตย์)'),
                                                                                        ('ทุกวัน (ไม่รวมเสาร์-อาทิตย์)',
                                                                                         'ทุกวัน (ไม่รวมเสาร์-อาทิตย์)'),
                                                                                        ('ทุกสัปดาห์', 'ทุกสัปดาห์')]
                                                      })
    iocode_id = db.Column('iocode_id', db.ForeignKey('iocodes.id'))
    occupancy = db.Column('occupancy', db.Integer())
    refreshment = db.Column('refreshment', db.Integer(), default=0)
    request = db.Column('request', db.Text(), info={'label': 'ความต้องการเพิ่มเติม'})
    approved = db.Column('approved', db.Boolean(), default=True)
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    creator = db.relationship('StaffAccount', foreign_keys=[created_by], backref=db.backref('room_reservations',
                                                                                            lazy='dynamic',
                                                                                            order_by='RoomEvent.start.desc()',
                                                                                            cascade='all, delete-orphan'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), server_default=None)
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True), server_default=None)
    cancelled_by = db.Column('cancelled_by', db.ForeignKey('staff_account.id'))
    approved_by = db.Column('approved_by', db.ForeignKey('staff_account.id'))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True), server_default=None)
    extra_items = db.Column('extra_items', db.JSON)
    note = db.Column('note', db.Text())
    comment = db.Column('comment', db.Text())
    iocode = db.relationship('IOCode', backref=db.backref('events', lazy='dynamic'))
    google_event_id = db.Column('google_event_id', db.String(64))
    google_calendar_id = db.Column('google_calendar_id', db.String(255))
    participants = db.relationship('StaffAccount', secondary=event_participant_assoc,
                                   backref=db.backref('events', lazy='dynamic'))
    notify_participants = db.Column('notify_participants', db.Boolean(), default=True)
    is_repeat_booking = db.Column('is_repeat_booking', db.Boolean(), default=False, info={'label': 'ทำการจองซ้ำ'})
    course_session_id = db.Column('course_session_id', db.ForeignKey('eduqa_course_sessions.id'))
    meeting_event_id = db.Column('meeting_event_id', db.ForeignKey('meeting_events.id'))
    master_id = db.Column('master_id', db.Integer, db.ForeignKey('scheduler_room_reservations.id'))
    secondary = db.relationship('RoomEvent', backref=db.backref('master', remote_side=[id]))

    @property
    def booked_rooms(self):
        """Rooms held by this event, with a legacy fallback during backfill."""
        if self.rooms:
            rooms_by_id = {room.id: room for room in self.rooms}
            if self.room and self.room.id not in rooms_by_id:
                rooms_by_id[self.room.id] = self.room
            ordered = []
            if self.room_id in rooms_by_id:
                ordered.append(rooms_by_id.pop(self.room_id))
            ordered.extend(sorted(rooms_by_id.values(), key=lambda room: room.number or ''))
            return ordered
        return [self.room] if self.room else []

    @property
    def room_names(self):
        return ' + '.join(room.number for room in self.booked_rooms)

    def to_dict(self):
        return {
            'room_number': self.room_names,
            'room_location': self.room.location,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'start': self.start.isoformat(),
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'end': self.end.isoformat(),
            'participants': len(self.participants) if self.participants else self.occupancy,
            'creator': self.creator.fullname if self.creator else None,
            'category': self.category.category if self.category else None,
            'note': self.note
        }

    def __str__(self):
        return f'{self.room.number}[ID={self.room.id}]: {self.start.isoformat()}-{self.end.isoformat()}'
