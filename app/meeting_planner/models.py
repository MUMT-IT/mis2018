from pytz import timezone
from sqlalchemy import func

from app.main import db
from app.staff.models import StaffAccount

Bangkok = timezone('Asia/Bangkok')


class MeetingEvent(db.Model):
    __tablename__ = 'meeting_events'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    title = db.Column('title', db.String(), nullable=False, info={'label': 'ชื่อ'})
    start = db.Column('start', db.DateTime(timezone=True), nullable=False, info={'label': 'เริ่ม'})
    end = db.Column('end', db.DateTime(timezone=True), nullable=False, info={'label': 'สิ้นสุด'})
    detail = db.Column('detail', db.Text(), info={'label': 'รายละเอียด'})
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('my_meetings'), foreign_keys=[creator_id])
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), server_default=None)
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True), server_default=None)
    cancelled_by = db.Column('cancelled_by', db.ForeignKey('staff_account.id'))
    notify_participants = db.Column('notify_participants', db.Boolean(), default=True,
                                    info={'label': 'แจ้งเตือนผู้เข้าร่วมประชุม'})
    meeting_events = db.relationship('RoomEvent')
    meeting_url = db.Column('meeting_url', db.Text(), info={'label': 'ลิงค์ประชุมออนไลน์'})

    @property
    def participants(self):
        return [i.staff.fullname for i in self.invitations]

    @property
    def rooms(self):
        return f'ห้อง {", ".join([e.room.number for e in self.meeting_events])}'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'start': self.start.astimezone(Bangkok).isoformat(),
            'end': self.end.astimezone(Bangkok).isoformat(),
            'rooms': self.rooms
        }


class MeetingInvitation(db.Model):
    __tablename__ = 'meeting_invitations'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    meeting_event_id = db.Column('meeting_event_id', db.ForeignKey('meeting_events.id'))
    meeting = db.relationship(MeetingEvent, backref=db.backref('invitations'))
    note = db.Column('note', db.Text(), default='')
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount,
                            backref=db.backref('invitations', lazy='dynamic', cascade='all, delete-orphan'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    responded_at = db.Column('responded_at', db.DateTime(timezone=True))
    response = db.Column('reponse', db.String(), info={'label': 'ตอบรับ'})


class MeetingAgenda(db.Model):
    __tablename__ = 'meeting_agendas'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    group = db.Column('group', db.String(), nullable=False,
                      info={'label': 'วาระ', 'choices': [(c, c) for c in ['แจ้งเพื่อทราบ',
                                                                          'เพื่อพิจารณา',
                                                                          'เรื่องสืบเนื่อง',
                                                                          'อื่นๆ']]})
    number = db.Column('number', db.String(), info={'label': 'ลำดับ'})
    detail = db.Column('detail', db.Text(), info={'label': 'หัวข้อ'})
    consensus = db.Column('consensus', db.Text())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True),
                           onupdate=func.now())
    consensus_updated_at = db.Column('consensus_updated_at', db.DateTime(timezone=True),
                                     onupdate=func.now())
    meeting_id = db.Column('meeting_id', db.ForeignKey('meeting_events.id'))
    meeting = db.relationship(MeetingEvent, backref=db.backref('agendas',
                                                               cascade='all, delete-orphan'))


class MeetingAgendaNote(db.Model):
    __tablename__ = 'meeting_agenda_notes'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    note = db.Column('note', db.Text())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('meeting_agenda_notes',
                                                             lazy='dynamic'))
