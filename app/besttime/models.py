from app.main import db
from app.staff.models import StaffAccount


date_time_assoc_table = db.Table('besttime_date_time_assoc_table',
                                 db.Column('datetime_slot_id', db.ForeignKey('datetime_slots.id')),
                                 db.Column('poll_vote_id', db.ForeignKey('poll_votes.id')))


class BestTimeDateTimeSlot(db.Model):
    __tablename__ = 'besttime_datetime_slots'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column(db.DateTime(timezone=True), nullable=False)
    end = db.Column(db.DateTime(timezone=True), nullable=False)
    poll_votes = db.relationship('PollVote', secondary=date_time_assoc_table, backref=db.backref('datetime_slots'))
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'))

    def __str__(self):
        return f'{self.start.strftime("%Y-%m-%d %H:%M")} to {self.end.strftime("%Y-%m-%d %H:%M")}'


class BestTimeMasterDateTimeSlot(db.Model):
    __tablename__ = 'besttime_master_datetime_slots'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column(db.DateTime(timezone=True), nullable=False)
    end = db.Column(db.DateTime(timezone=True), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'))
    poll = db.relationship('Poll', backref=db.backref('master_datetime_slots', cascade='all, delete-orphan',
                                                      lazy='dynamic', order_by='MasterDateTimeSlot.start'))
    is_active = db.Column(db.Boolean, default=True)

    def __str__(self):
        return f'{self.start.strftime("%Y-%m-%d %H:%M")} to {self.end.strftime("%Y-%m-%d %H:%M")}'

class BestTimePoll(db.Model):
    __tablename__ = 'besttime_polls'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(), nullable=False, info={'label': 'Title'})
    start_date = db.Column(db.Date(), nullable=False, info={'label': 'Start Date'})
    desc = db.Column(db.Text(), info={'label': 'Description'})
    end_date = db.Column(db.Date(), nullable=False, info={'label': 'End Date'})
    creator_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=False)
    creator = db.relationship('User', backref=db.backref('polls'))
    created_at = db.Column(db.DateTime(timezone=True))
    modified_at = db.Column(db.DateTime(timezone=True))
    closed_at = db.Column(db.DateTime(timezone=True))

    def __str__(self):
        return f'{self.title}'

    @property
    def date_span(self):
        return f'{self.start_date.strftime("%d/%m/%Y")} to {self.end_date.strftime("%d/%m/%Y")}'

    @property
    def voted(self):
        return [i for i in self.invitations if i.voted_at]

    @property
    def active_master_datetime_slots(self):
        return self.master_datetime_slots.filter(BestTimeMasterDateTimeSlot.start >= self.start_date)\
            .filter(BestTimeMasterDateTimeSlot.end <= self.end_date)


class BestTimePollMessage(db.Model):
    __tablename__ = 'besttime_poll_messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message = db.Column(db.String(), info={'label': 'Message'})
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    poll = db.relationship(BestTimePoll, backref=db.backref('messages'))
    voter_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=False)
    voter = db.relationship(StaffAccount, backref=db.backref('messages'))
    created_at = db.Column(db.DateTime(timezone=True))


class BestTimePollVote(db.Model):
    __tablename__ = 'besttime_poll_votes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    voter = db.relationship(StaffAccount, backref=db.backref('votes'))
    poll = db.relationship(BestTimePoll, backref=db.backref('invitations', lazy='dynamic'))
    last_notified = db.Column(db.DateTime(timezone=True))  # update this every time the notification is sent
    voted_at = db.Column(db.DateTime(timezone=True))
    num_notifications = db.Column(db.Integer(), default=0)
    role = db.Column(db.String(), info={'label': 'Role',
                                        'choices': [(r, r) for r in ['committee', 'chairman']]})