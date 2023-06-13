from app.main import db
from app.staff.models import StaffAccount


class PARound(db.Model):
    __tablename__ = 'pa_rounds'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column('start', db.Date())
    end = db.Column('end', db.Date())


class PAAgreement(db.Model):
    __tablename__ = 'pa_agreements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('pa_agreements', cascade='all, delete-orphan'))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    round_id = db.Column('round_id', db.ForeignKey('pa_rounds.id'))
    round = db.relationship(PARound, backref=db.backref('agreements', lazy='dynamic'))
