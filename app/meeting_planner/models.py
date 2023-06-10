from sqlalchemy import func

from app.main import db
from app.staff.models import StaffAccount


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
    notify_participants = db.Column('notify_participants', db.Boolean(), default=True, info={'label': 'แจ้งเตือนผู้เข้าร่วมประชุม'})


class MeetingInvitation(db.Model):
    __tablename__ = 'meeting_invitations'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    meeting_event_id = db.Column('meeting_event_id', db.ForeignKey('meeting_events.id'))
    meeting = db.relationship(MeetingEvent, backref=db.backref('invitations'))
    note = db.Column('note', db.Text())
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount,
                            backref=db.backref('invitations', lazy='dynamic', cascade='all, delete-orphan'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    responded_at = db.Column('responded_at', db.DateTime(timezone=True))
    response = db.Column('reponse', db.String(), info={'label': 'ตอบรับ'})

