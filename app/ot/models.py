# -*- coding:utf-8 -*-

from ..main import db
from pytz import timezone
from app.models import Org
from app.staff.models import StaffAccount
from datetime import datetime


class OtPaymentAnnounce(db.Model):
    __tablename__ = 'ot_payment_announce'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String())
    upload_file_url = db.Column('upload_file_url', db.String())
    created_account_id = db.Column('created_account_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('ot_announcement'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=datetime.now())
    announce_at = db.Column('announce_at', db.Date(), nullable=False)
    start_date = db.Column('start_date', db.Date(), nullable=False)
    end_date = db.Column('end_date', db.Date(), nullable=True)
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))


# class OtPaymentDetail(db.Model):
#     __tablename__ = 'ot_payment_detail'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     announce_id = db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'))
#     work_at_org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
#     work_at_org = db.relationship(Org, backref=db.backref('ot_rate'))
#     role = db.Column('role', db.String())
#     per_period = db.Column('per_period', db.Integer())
#     per_hour = db.Column('per_hour', db.Integer())
#     is_faculty_employer = db.Column('is_faculty_employer', db.Boolean(), default=True)
#     can_duplicate = db.Column('can_duplicate', db.Boolean(), default=True)


# class OtDocumentApproval(db.Model):
#     __tablename__ = 'ot_document_approval'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     approval_no = db.Column('approval_no', db.String())
#     approved_date = db.Column('approved_date', db.Date(), nullable=True)
#     created_at = db.Column('created_at',db.DateTime(timezone=True),default=datetime.now())
#     start_date = db.Column('start_date', db.Date(), nullable=True)
#     end_date = db.Column('end_date', db.Date(), nullable=True)
#     cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
#     org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
#     org = db.relationship(Org, backref=db.backref('document_approval'))
#     upload_file_url = db.Column('upload_file_url', db.String())
#     io_no
#     cost_no
#
#
# class OtApprovalDetail(db.Model):
#     __tablename__ = 'ot_approval_detail'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     doc_id = db.Column('doc_id', db.ForeignKey('ot_document_approval.id'))
#     role = db.Column('role', db.String())
#
#
# class OtPerson(db.Model):
#     __tablename__ = 'ot_document_approval'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     doc_id = db.Column('doc_id', db.ForeignKey('ot_document_approval.id'))
#     created_at = db.Column('created_at',db.DateTime(timezone=True),default=datetime.now())
#     staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
#     staff = db.relationship(StaffAccount, backref=db.backref('ot_person'))


