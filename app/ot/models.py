# -*- coding:utf-8 -*-
import pytz
from psycopg2._range import DateTimeRange
from sqlalchemy import func

from ..main import db
from pytz import timezone
from sqlalchemy_utils import DateTimeRangeType
from app.models import Org
from app.staff.models import StaffAccount
from datetime import datetime, timedelta

ot_announce_document_assoc_table = db.Table('ot_announce_document_assoc',
                                            db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'),
                                                      primary_key=True),
                                            db.Column('document_id', db.ForeignKey('ot_document_approval.id'),
                                                      primary_key=True),
                                            )


ot_staff_assoc_table = db.Table('ot_staff_assoc',
                                db.Column('staff_id', db.ForeignKey('staff_account.id'), primary_key=True),
                                db.Column('document_id', db.ForeignKey('ot_document_approval.id'),
                                          primary_key=True),
                                )


class OtPaymentAnnounce(db.Model):
    __tablename__ = 'ot_payment_announce'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(), info={'label': u'เรื่อง'})
    file_name = db.Column('file_name', db.String())
    upload_file_url = db.Column('upload_file_url', db.String())
    created_account_id = db.Column('created_account_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('ot_announcement'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=datetime.now())
    announce_at = db.Column('announce_at', db.DateTime(timezone=True), info={'label': u'ประกาศเมื่อ'})
    start_datetime = db.Column('start_datetime', db.DateTime(timezone=True), info={'label': u'เริ่มใช้ตั้งแต่'})
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    org_id = db.Column('org_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org)

    def __str__(self):
        return self.topic


class OtCompensationRate(db.Model):
    __tablename__ = 'ot_compensation_rate'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    announce_id = db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'))
    announcement = db.relationship(OtPaymentAnnounce, backref=db.backref('ot_rate'))
    work_at_org_id = db.Column('work_at_org_id', db.ForeignKey('orgs.id'))
    work_for_org_id = db.Column('work_for_org_id', db.ForeignKey('orgs.id'))
    work_at_org = db.relationship(Org, backref=db.backref('ot_work_at_rate'), foreign_keys=[work_at_org_id])
    work_for_org = db.relationship(Org, backref=db.backref('ot_work_for_rate'), foreign_keys=[work_for_org_id])
    role = db.Column('role', db.String(), info={'label': u'ตำแหน่ง'})
    per_period = db.Column('per_period', db.Integer(), info={'label': u'ต่อคาบ'})
    per_hour = db.Column('per_hour', db.Integer(), info={'label': u'ต่อชั่วโมง'})
    per_day = db.Column('per_day', db.Integer(), info={'label': u'ต่อวัน'})
    is_faculty_emp = db.Column('is_faculty_emp', db.Boolean(), info={'label': u'บุคลากรสังกัดคณะ'})
    is_workday = db.Column('is_workday', db.Boolean(), default=True, nullable=False, info={'label': u'นอกเวลาราชการ'})
    max_hour = db.Column('max_hour', db.Integer(), info={'label': u'จำนวนชั่วโมงสูงสุดที่สามารถทำได้'})
    double_payment = db.Column('double_payment', db.Boolean(), default=True, nullable=False,
                               info={'label': u'เบิกซ้ำกับอันอื่นได้'})
    is_role_required = db.Column('is_role_required', db.Boolean(), info={'label': u'จำเป็นต้องระบุรายละเอียดตำแหน่ง'})
    is_count_in_mins = db.Column('is_count_in_mins', db.Boolean(), info={'label': u'คำนวณเป็นนาที'})
    topup = db.Column('topup', db.Numeric(), default=0.0, info={'label': u'ค่าผลัด/เงินเพิ่ม'})
    detail = db.Column('detail', db.String())
    abbr = db.Column('abbr', db.String())
    timeslot_id = db.Column('timeslot_id', db.ForeignKey('ot_timeslots.id'))
    time_slot = db.relationship('OtTimeSlot')
    ot_job_role_id = db.Column('ot_job_role_id', db.ForeignKey('ot_job_roles.id'))
    ot_job_role = db.relationship('OtJobRole', backref=db.backref('ot_rates'))

    def __str__(self):
        return f'{self.ot_job_role}: {self.per_hour or self.per_day or self.per_period or ""}{self.unit}'

    @property
    def unit(self):
        if self.per_day:
            return 'ต่อวัน'
        elif self.per_period:
            return 'ต่อคาบ'
        elif self.per_hour:
            return 'ต่อชม.'
        else:
            return ''

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'announcement': self.announcement.topic,
            'work_at_org': self.work_at_org.name,
            'work_for_org': self.work_for_org.name,
            'per_period': self.per_period,
            'per_hour': self.per_hour,
            'per_day': self.per_day,
            'is_workday': self.is_workday,
            'is_role_required': self.is_role_required,
        }


class OtTimeSlot(db.Model):
    """
    Timeslots are valid as long as an announcement is valid.
    """
    __tablename__ = 'ot_timeslots'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    start = db.Column('start', db.Time(), nullable=False)
    end = db.Column('end', db.Time(), nullable=False)
    announcement_id = db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'))
    announcement = db.relationship(OtPaymentAnnounce, backref=db.backref('timeslots'))
    retired_at = db.Column('retired_at', db.DateTime(timezone=True))
    work_for_org_id = db.Column('work_for_org_id', db.ForeignKey('orgs.id'))
    work_for_org = db.relationship(Org)
    color = db.Column(db.String())

    def __str__(self):
        return f'{self.start} - {self.end} {self.work_for_org}'

    def __repr__(self):
        return str(self)


class OtJobRole(db.Model):
    """
    Job roles are valid as long as an announcement is valid.
    """
    __tablename__ = 'ot_job_roles'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    role = db.Column('job_role', db.String(), nullable=False)
    announce_id = db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'))
    announcement = db.relationship(OtPaymentAnnounce, backref=db.backref('job_roles'))
    retired_at = db.Column('retired_at', db.DateTime(timezone=True))
    work_for_org_id = db.Column('work_for_org_id', db.ForeignKey('orgs.id'))
    work_for_org = db.relationship(Org)

    def __str__(self):
        return f'{self.role}'


class OtShift(db.Model):
    __tablename__ = 'ot_shifts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    datetime = db.Column(DateTimeRangeType(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    timeslot_id = db.Column('timeslot_id', db.ForeignKey('ot_timeslots.id'))
    timeslot = db.relationship(OtTimeSlot, backref=db.backref('shifts'))
    creator = db.relationship(StaffAccount)

    def __init__(self, date, timeslot, creator):
        start = datetime.combine(date, timeslot.start, tzinfo=pytz.timezone('Asia/Bangkok'))
        end = datetime.combine(date, timeslot.end, tzinfo=pytz.timezone('Asia/Bangkok'))
        if timeslot.end.hour == 0 and timeslot.end.minute == 0:
            end += timedelta(days=1)
        self.datetime = DateTimeRange(lower=start, upper=end, bounds='[)')
        self.creator = creator
        self.timeslot = timeslot

    def __str__(self):
        return f'{self.datetime.lower.time()} - {self.datetime.upper.time()}'


class OtDocumentApproval(db.Model):
    __tablename__ = 'ot_document_approval'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), info={'label': u'เรื่อง'})
    approval_no = db.Column('approval_no', db.String(), info={'label': u'เลขที่หนังสือ'})
    approved_date = db.Column('approved_date', db.Date(), nullable=True, info={'label': u'วันที่อนุมัติ'})
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=datetime.now())
    start_datetime = db.Column('start_datetime', db.DateTime(), nullable=False, info={'label': u'เริ่มต้นการอนุมัติ'})
    end_datetime = db.Column('end_datetime', db.DateTime(), info={'label': u'สิ้นสุดการอนุมัติ'})
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('document_approval'))
    upload_file_url = db.Column('upload_file_url', db.String())
    file_name = db.Column('file_name', db.String())
    created_staff_id = db.Column('created_staff_id', db.ForeignKey('staff_account.id'))
    created_staff = db.relationship(StaffAccount, backref=db.backref('ot_approval'))
    announce = db.relationship('OtPaymentAnnounce',
                               secondary=ot_announce_document_assoc_table,
                               backref=db.backref('document_approval', lazy='dynamic'))
    staff = db.relationship('StaffAccount',
                            secondary=ot_staff_assoc_table,
                            backref=db.backref('document_approval_staff', lazy='dynamic'))

    #    cost_center_id = db.Column('cost_center_id', db.ForeignKey('cost_centers.id'))
    #    io_code = db.Column('io_code', db.ForeignKey('iocodes.id'))
    def __str__(self):
        return self.title


class OtRecord(db.Model):
    __tablename__ = 'ot_record'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('ot_record_staff'), foreign_keys=[staff_account_id])
    compensation_id = db.Column('compensation_id', db.ForeignKey('ot_compensation_rate.id'))
    compensation = db.relationship(OtCompensationRate, backref=db.backref('ot_records'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    created_account_id = db.Column('created_account_id', db.ForeignKey('staff_account.id'))
    created_staff = db.relationship(StaffAccount, backref=db.backref('ot_record_created_staff'),
                                    foreign_keys=[created_account_id])
    org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('ot_records'))
    sub_role = db.Column('sub_role', db.String())
    document_id = db.Column('document_id', db.ForeignKey('ot_document_approval.id'))
    document = db.relationship(OtDocumentApproval, backref=db.backref('ot_records'))
    round_id = db.Column('round_id', db.ForeignKey('ot_round_request.id'))
    round = db.relationship('OtRoundRequest', backref=db.backref('ot_records'))
    canceled_at = db.Column('canceled_at', db.DateTime(timezone=True), default=datetime.now())
    canceled_by_account_id = db.Column('canceled_by_account_id', db.ForeignKey('staff_account.id'))
    total_hours = db.Column('total_hours', db.Integer())
    total_minutes = db.Column('total_minutes', db.Integer())
    amount_paid = db.Column('amount_paid', db.Float())
    extra = db.Column('extra', db.Numeric(), default=0)

    shift_id = db.Column('shift_id', db.ForeignKey('ot_shifts.id'))
    shift = db.relationship(OtShift, backref=db.backref('records'))

    @property
    def total_hours(self):
        timeslot = self.shift.timeslot
        hours = timeslot.end.hour - timeslot.start.hour
        minutes = timeslot.end.minute + timeslot.start.minute

        return (hours * 60) + minutes

    def calculate_total_pay(self, mins):
        if self.compensation.per_hour:
            return (mins/60.0) * self.compensation.per_hour

    def count_rate(self):
        if self.compensation.per_hour:
            if self.compensation.is_count_in_mins:
                per_min = self.compensation.per_hour / 60
                rate = self.total_ot_hours() * per_min
            else:
                rate = self.total_ot_hours() * self.compensation.per_hour
        elif self.compensation.per_period:
            rate = self.compensation.per_period
        else:
            rate = self.compensation.per_day
        return rate

    def list_records(self):
        return [self.compensation.role,
                self.staff.personal_info.fullname,
                self.start_datetime,
                self.end_datetime,
                self.total_hours or self.total_minutes,
                100,
                ]


class OtRoundRequest(db.Model):
    __tablename__ = 'ot_round_request'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    round_no = db.Column('round_no', db.String())
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=datetime.now())
    created_by_account_id = db.Column('created_by_account_id', db.ForeignKey('staff_account.id'))
    created_by = db.relationship(StaffAccount, backref=db.backref('ot_round_created_by'),
                                 foreign_keys=[created_by_account_id])
    approval_at = db.Column('approval_at', db.DateTime(timezone=True))
    approval_by_account_id = db.Column('approval_by_account_id', db.ForeignKey('staff_account.id'))
    approval_by = db.relationship(StaffAccount, backref=db.backref('ot_round_approval_by'),
                                  foreign_keys=[approval_by_account_id])
    verified_at = db.Column('verified_at', db.DateTime(timezone=True))
    verified_by_account_id = db.Column('verified_by_account_id', db.ForeignKey('staff_account.id'))
    verified_by = db.relationship(StaffAccount, backref=db.backref('ot_round_verified_by'),
                                  foreign_keys=[verified_by_account_id])

