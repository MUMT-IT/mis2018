from sqlalchemy.orm import relationship

from app.main import db
from app.staff.models import StaffAccount


date_time_assoc_table = db.Table('besttime_date_time_assoc_table',
                                 db.Column('datetime_slot_id', db.ForeignKey('besttime_datetime_slots.id')),
                                 db.Column('poll_vote_id', db.ForeignKey('besttime_poll_votes.id')))


poll_admin_assoc_table = db.Table('besttime_poll_admin_assoc_table',
                                 db.Column('staff_account_id', db.ForeignKey('staff_account.id')),
                                 db.Column('poll_id', db.ForeignKey('besttime_polls.id')))

from zoneinfo import ZoneInfo

BKK_TZ = ZoneInfo('Asia/Bangkok')


class BestTimeDateTimeSlot(db.Model):
    __tablename__ = 'besttime_datetime_slots'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column(db.DateTime(timezone=True), nullable=False)
    end = db.Column(db.DateTime(timezone=True), nullable=False)
    poll_votes = db.relationship('BestTimePollVote', secondary=date_time_assoc_table, backref=db.backref('datetime_slots'))
    poll_id = db.Column(db.Integer, db.ForeignKey('besttime_polls.id'))
    # The relationship is added to allow cascade delete, not intended to be used directly.
    poll = db.relationship('BestTimePoll', backref=db.backref('_datetime_slots', cascade='all, delete-orphan'))
    is_best = db.Column(db.Boolean(), nullable=True, default=False)

    def __str__(self):
        return f'{self.start.astimezone(BKK_TZ).strftime("%d/%m/%Y %H:%M")} - {self.end.astimezone(BKK_TZ).strftime("%H:%M น.")}'

    @property
    def has_valid_committee(self):
        has_chairman = len([vote for vote in self.poll_votes if vote.role=='chairman']) > 0
        valid_number = len(self.poll_votes) >= (self.poll.invitations.count()/2)
        return valid_number and has_chairman

    def get_voter_names(self):
        return [vote.voter.fullname for vote in self.poll_votes]


class BestTimeMasterDateTimeSlot(db.Model):
    __tablename__ = 'besttime_master_datetime_slots'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column(db.DateTime(timezone=True), nullable=False)
    end = db.Column(db.DateTime(timezone=True), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('besttime_polls.id'))
    poll = db.relationship('BestTimePoll', backref=db.backref('master_datetime_slots', cascade='all, delete-orphan',
                                                      lazy='dynamic', order_by='BestTimeMasterDateTimeSlot.start'))
    is_active = db.Column(db.Boolean, default=True)

    def __str__(self):
        return f'{self.start.astimezone(BKK_TZ).strftime("%Y-%m-%d %H:%M")} to {self.end.astimezone(BKK_TZ).strftime("%Y-%m-%d %H:%M")}'

class BestTimePoll(db.Model):
    __tablename__ = 'besttime_polls'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(), nullable=False, info={'label': 'ชื่อแบบสำรวจ'})
    start_date = db.Column(db.Date(), nullable=False, info={'label': 'วันที่ตัวเลือกเริ่มต้น'})
    desc = db.Column(db.Text(), info={'label': 'รายละเอียด'})
    end_date = db.Column(db.Date(), nullable=False, info={'label': 'วันที่ตัวเลือกสุดท้าย'})
    creator_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=False)
    creator = db.relationship(StaffAccount, backref=db.backref('besttime_polls'))
    created_at = db.Column(db.DateTime(timezone=True))
    modified_at = db.Column(db.DateTime(timezone=True))
    closed_at = db.Column(db.DateTime(timezone=True))
    admins = db.relationship(StaffAccount, secondary=poll_admin_assoc_table, backref=db.backref('besttime_poll_admins'))
    vote_start_date = db.Column('vote_start_date', db.Date(), nullable=False, info={'label': 'วันเริ่มการโหวต'})
    vote_end_date = db.Column('vote_end_date', db.Date(), nullable=False, info={'label': 'วันสิ้นสุดการโหวต'})


    def __str__(self):
        return f'{self.title}'

    @property
    def date_span(self):
        return f'{self.start_date.strftime("%d/%m/%Y")} - {self.end_date.strftime("%d/%m/%Y")}'

    @property
    def vote_date_span(self):
        return f'{self.vote_start_date.strftime("%d/%m/%Y")} - {self.vote_end_date.strftime("%d/%m/%Y")}'

    @property
    def voted(self):
        return [i for i in self.invitations if i.voted_at]

    @property
    def active_master_datetime_slots(self):
        return self.master_datetime_slots.filter(BestTimeMasterDateTimeSlot.start >= self.start_date)\
            .filter(BestTimeMasterDateTimeSlot.end <= self.end_date)

    def has_admin_role(self, account):
        return (self.creator == account) or (account in self.admins)

    @property
    def is_completed(self):
        return self.invitations.count() == self.invitations.filter(BestTimePollVote.voted_at!=None).count()

    @property
    def has_valid_slots(self):
        return len([slot for slot in self._datetime_slots if slot.has_valid_committee]) > 0

    def get_chairman(self):
        vote = self.invitations.filter_by(role='chairman').first()
        return vote.voter if vote else None


class BestTimePollMessage(db.Model):
    __tablename__ = 'besttime_poll_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message = db.Column(db.String(), info={'label': 'Message'})
    poll_id = db.Column(db.Integer, db.ForeignKey('besttime_polls.id'), nullable=False)
    poll = db.relationship(BestTimePoll, backref=db.backref('messages', cascade='all, delete-orphan'))
    voter_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=False)
    voter = db.relationship(StaffAccount, backref=db.backref('messages'))
    created_at = db.Column(db.DateTime(timezone=True))


class BestTimePollVote(db.Model):
    __tablename__ = 'besttime_poll_votes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('besttime_polls.id'), nullable=False)
    voter = db.relationship(StaffAccount, backref=db.backref('votes'))
    poll = db.relationship(BestTimePoll, backref=db.backref('invitations', lazy='dynamic', cascade='all, delete-orphan'))
    last_notified = db.Column(db.DateTime(timezone=True))  # update this every time the notification is sent
    voted_at = db.Column(db.DateTime(timezone=True))
    num_notifications = db.Column(db.Integer(), default=0)
    role = db.Column(db.String(), info={'label': 'Role',
                                        'choices': [(r, r) for r in ['committee', 'chairman']]})