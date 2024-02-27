# -*- coding:utf-8 -*-
from sqlalchemy import func

from app.main import db
from app.procurement.models import ProcurementDetail
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


complaint_record_room_assoc = db.Table('complaint_record_room_assoc',
                                          db.Column('id', db.Integer, autoincrement=True, primary_key=True),
                                          db.Column('room_id', db.Integer, db.ForeignKey('scheduler_room_resources.id')),
                                          db.Column('record_id', db.Integer, db.ForeignKey('complaint_records.id'))
                                          )

complaint_record_procurement_assoc = db.Table('complaint_record_procurement_assoc',
                                              db.Column('id', db.Integer, autoincrement=True, primary_key=True),
                                              db.Column('procurement_id', db.Integer, db.ForeignKey('procurement_details.id')),
                                              db.Column('record_id', db.Integer, db.ForeignKey('complaint_records.id'))
                                              )


class ComplaintCategory(db.Model):
    __tablename__ = 'complaint_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column('category', db.String(255), nullable=False)

    def __str__(self):
        return u'{}'.format(self.category)


class ComplaintTopic(db.Model):
    __tablename__ = 'complaint_topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(255), nullable=False)
    code = db.Column('code', db.String())
    category_id = db.Column('category_id', db.ForeignKey('complaint_categories.id'))
    category = db.relationship(ComplaintCategory, backref=db.backref('topics', cascade='all, delete-orphan'))

    def __str__(self):
        return u'{}'.format(self.topic)


class ComplaintSubTopic(db.Model):
    __tablename__ = 'complaint_sub_topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subtopic = db.Column('subtopic', db.String())
    topic_id = db.Column('topic_id', db.ForeignKey('complaint_topics.id'))
    topic = db.relationship(ComplaintTopic, backref=db.backref('subtopics', cascade='all, delete-orphan'))

    def __str__(self):
        return '{}'.format(self.subtopic)


class ComplaintAdmin(db.Model):
    __tablename__ = 'complaint_admins'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account = db.Column('staff_account', db.ForeignKey('staff_account.id'))
    is_supervisor = db.Column('is_supervisor', db.Boolean(), default=False)
    topic_id = db.Column('topic_id', db.ForeignKey('complaint_topics.id'))
    topic = db.relationship(ComplaintTopic, backref=db.backref('admins', cascade='all, delete-orphan'))
    admin = db.relationship(StaffAccount)

    def __str__(self):
        return u'{}'.format(self.admin.fullname)


class ComplaintPriority(db.Model):
    __tablename__ = 'complaint_priorities'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    priority = db.Column('priority', db.Integer, nullable=False)
    priority_text = db.Column('priority_text', db.String(255), nullable=False)

    def __str__(self):
        return u'{}'.format(self.priority_text)


class ComplaintStatus(db.Model):
    __tablename__ = 'complaint_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    status = db.Column('status', db.String(), nullable=False)
    icon = db.Column('icon', db.String())
    color = db.Column('color', db.String())

    def __str__(self):
        return u'{}'.format(self.status)


class ComplaintRecord(db.Model):
    __tablename__ = 'complaint_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    desc = db.Column('desc', db.Text(), nullable=False, info={'label': u'รายละเอียด'})
    appeal = db.Column('appeal', db.Boolean(), default=False, info={'label': 'ร้องเรียน'})
    topic_id = db.Column('topic_id', db.ForeignKey('complaint_topics.id'))
    topic = db.relationship(ComplaintTopic, backref=db.backref('records', cascade='all, delete-orphan'))
    priority_id = db.Column('priority_id', db.ForeignKey('complaint_priorities.id'))
    priority = db.relationship(ComplaintPriority, backref=db.backref('records', cascade='all, delete-orphan'))
    status_id = db.Column('status', db.ForeignKey('complaint_statuses.id'))
    status = db.relationship(ComplaintStatus, backref=db.backref('records', cascade='all, delete-orphan'))
    origin_id = db.Column('origin_id', db.ForeignKey('complaint_records.id'))
    children = db.relationship('ComplaintRecord', backref=db.backref('parent', remote_side=[id]))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    rooms = db.relationship(RoomResource, secondary=complaint_record_room_assoc, backref=db.backref('complaint_records'))
    procurements = db.relationship(ProcurementDetail, secondary=complaint_record_procurement_assoc,
                                   backref=db.backref('complaint_records'))
    subtopic_id = db.Column('subtopic_id', db.ForeignKey('complaint_sub_topics.id'))
    subtopic = db.relationship(ComplaintSubTopic, backref=db.backref('records', cascade='all, delete-orphan'))


class ComplaintActionRecord(db.Model):
    __tablename__ = 'complaint_action_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('actions', cascade='all, delete-orphan'))
    reviewer_id = db.Column('reviewer_id', db.ForeignKey('complaint_admins.id'))
    reviewer = db.relationship(ComplaintAdmin, backref=db.backref('actions', cascade='all, delete-orphan'),
                               foreign_keys=[reviewer_id])
    review_comment = db.Column('review_comment', db.Text(), info={'label': u'บันทึกจากผู้รีวิว'})
    approver_id = db.Column('approver_id', db.ForeignKey('complaint_admins.id'))
    approver = db.relationship(ComplaintAdmin, foreign_keys=[approver_id])
    approved = db.Column('approved', db.DateTime(timezone=True))
    approver_comment = db.Column('approver_comment', db.Text())
    deadline = db.Column('deadline', db.DateTime(timezone=True))


class ComplaintInvestigator(db.Model):
    __tablename__ = 'complaint_forwards'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    admin_id = db.Column('admin_id', db.ForeignKey('complaint_admins.id'))
    admin = db.relationship(ComplaintAdmin, backref=db.backref('investigators', cascade='all, delete-orphan'))
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('investigators', cascade='all, delete-orphan'))