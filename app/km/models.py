from app.main import db
from sqlalchemy.sql import func
from app.staff.models import StaffAccount


class KMProcess(db.Model):
    __tablename__ = 'km_processes'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    # naming a field as process breaks wtforms
    process_name = db.Column('process', db.String(), nullable=False)
    desc = db.Column('desc', db.Text())
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    obsolete = db.Column('obsolete', db.Boolean(), default=False, nullable=False)

    creator = db.relationship(StaffAccount, backref=db.backref('km_processes'))


class KMTopic(db.Model):
    __tablename__ = 'km_topics'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(), nullable=False)
    desc = db.Column('desc', db.Text())
    process_id = db.Column('process_id', db.ForeignKey('km_processes.id'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    obsolete = db.Column('obsolete', db.Boolean(), default=False, nullable=False)

    creator = db.relationship(StaffAccount, backref=db.backref('km_topics'))
    # naming a field as process breaks wtforms
    km_process = db.relationship(KMProcess, backref=db.backref('topics'))


#TODO: add knowledge model
#TODO: add an activity model for each knowledge
#TODO: add source model