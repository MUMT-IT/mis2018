# -*- coding:utf-8 -*-
from ..main import db,ma
from werkzeug import generate_password_hash, check_password_hash
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import timezone
from marshmallow import fields
from app.models import OrgSchema
from datetime import datetime, timedelta
from app.main import get_weekdays
import numpy as np


def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = u'%d/%m/%Y %H:%M'
    return dt.astimezone(bangkok).strftime(datetime_format)


class StaffAccount(db.Model):
    __tablename__ = 'staff_account'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    personal_id = db.Column('personal_id', db.ForeignKey('staff_personal_info.id'))
    email = db.Column('email', db.String(), unique=True)
    personal_info = db.relationship("StaffPersonalInfo", backref=db.backref("staff_account", uselist=False))
    line_id = db.Column('line_id', db.String(), index=True, unique=True)
    __password_hash = db.Column('password', db.String(255), nullable=True)

    @property
    def password(self):
        raise AttributeError('Password attribute is not accessible.')

    @password.setter
    def password(self, password):
        self.__password_hash = generate_password_hash(password)

    def verify_password(self, password):
        if not self.__password_hash:
            return False
        return check_password_hash(self.__password_hash, password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def __str__(self):
        return u'{}'.format(self.email)

    @property
    def total_wfh_duration(self):
        return sum([wfh.duration for wfh in self.wfh_requests if not wfh.cancelled_at and wfh.get_approved])


class StaffPersonalInfo(db.Model):
    __tablename__ = 'staff_personal_info'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    en_firstname = db.Column('en_firstname', db.String(), nullable=False)
    en_lastname = db.Column('en_lastname', db.String(), nullable=False)
    highest_degree_id = db.Column('highest_degree_id', db.ForeignKey('staff_edu_degree.id'))
    highest_degree = db.relationship('StaffEduDegree',
                        backref=db.backref('staff_personal_info', uselist=False))
    th_firstname = db.Column('th_firstname', db.String(), nullable=True)
    th_lastname = db.Column('th_lastname', db.String(), nullable=True)
    academic_position_id = db.Column('academic_position_id', db.ForeignKey('staff_academic_position.id'))
    academic_position = db.relationship('StaffAcademicPosition', backref=db.backref('staff_list'))
    org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
    org = db.relationship('Org', backref=db.backref('staff'))
    employed_date = db.Column('employed_date', db.Date(), nullable=True)
    employment_id = db.Column('employment_id',
                              db.ForeignKey('staff_employments.id'))
    employment = db.relationship('StaffEmployment',
                                 backref=db.backref('staff'))

    def __str__(self):
        return u'{} {}'.format(self.th_firstname, self.th_lastname)


    @property
    def fullname(self):
        return u'{} {}'.format(self.th_firstname, self.th_lastname)


    def get_employ_period(self):
        today = datetime.now().date()
        period = relativedelta(today, self.employed_date)
        return period

    @property
    def is_eligible_for_leave(self, minmonth=6.0):
        period = self.get_employ_period()
        if period.years > 0:
            return True
        elif period.years == 0 and period.months > minmonth:
            return True
        else:
            return False

    def get_max_cum_quota_per_year(self, leave_quota):
        period = self.get_employ_period()
        if self.is_eligible_for_leave:
            if period.years < 10:
                return leave_quota.cum_max_per_year1
            else:
                return leave_quota.cum_max_per_year2
        else:
            return 0

    def get_total_leaves(self, leave_quota_id, start_date=None, end_date=None):
        total_leaves = []
        for req in self.staff_account.leave_requests:
            if req.quota.id == leave_quota_id:
                if start_date is None or end_date is None:
                    if not req.cancelled_at and req.get_approved:
                        total_leaves.append(req.total_leave_days)
                else:
                    if req.start_datetime >= start_date and req.end_datetime <= end_date:
                        if not req.cancelled_at and req.get_approved:
                            total_leaves.append(req.total_leave_days)

        return sum(total_leaves)
        #return len([req for req in self.staff_account.leave_requests if req.quota_id == leave_quota_id])


class StaffEduDegree(db.Model):
    __tablename__ = 'staff_edu_degree'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    level = db.Column('level', db.String(), nullable=False)
    en_title = db.Column('en_title', db.String())
    th_title = db.Column('th_title', db.String())
    en_major = db.Column('en_major', db.String())
    th_major = db.Column('th_major', db.String())
    en_school = db.Column('en_school', db.String())
    th_country = db.Column('th_country', db.String())


class StaffAcademicPosition(db.Model):
    __tablename__ = 'staff_academic_position'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    fullname_th = db.Column('fullname_th', db.String(), nullable=False)
    shortname_th = db.Column('shortname_th', db.String(), nullable=False)
    fullname_en = db.Column('fullname_en', db.String(), nullable=False)
    shortname_en = db.Column('shortname_en', db.String(), nullable=False)
    level = db.Column('level', db.Integer(), nullable=False)


class StaffEmployment(db.Model):
    __tablename__ = 'staff_employments'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), unique=True, nullable=False)

    def __str__(self):
        return self.title


class StaffLeaveType(db.Model):
    __tablename__ = 'staff_leave_types'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    type_ = db.Column('type', db.String(), nullable=False, unique=True)
    request_in_advance = db.Column('request_in_advance', db.Boolean())
    document_required = db.Column('document_required', db.Boolean(), default=False)
    reason_required = db.Column('reason_required', db.Boolean())

    def __str__(self):
        return self.type_

    def __repr__(self):
        return self.type_


class StaffLeaveQuota(db.Model):
    __tablename__ = 'staff_leave_quota'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    first_year = db.Column('first_year', db.Integer())
    max_per_leave = db.Column('max_per_leave', db.Integer())
    max_per_year = db.Column('max_per_year', db.Integer())
    cum_max_per_year1 = db.Column('cum_max_per_year1', db.Integer())
    cum_max_per_year2 = db.Column('cum_max_per_year2', db.Integer())
    min_employed_months = db.Column('min_employed_months', db.Integer())
    employment_id = db.Column('employment_id', db.ForeignKey('staff_employments.id'))
    leave_type_id = db.Column('leave_type_id', db.ForeignKey('staff_leave_types.id'))
    leave_type = db.relationship('StaffLeaveType', backref=db.backref('quota'))
    employment = db.relationship('StaffEmployment', backref=db.backref('quota'))

    def __str__(self):
        return u'{}:{}:{}'.format(self.employment.title,
                                  self.leave_type.type_,
                                  self.cum_max_per_year2)


class StaffLeaveRequest(db.Model):
    __tablename__ = 'staff_leave_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    leave_quota_id = db.Column('quota_id', db.ForeignKey('staff_leave_quota.id'))
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    #TODO: fixed offset-naive and offset-timezone comparison error.
    start_datetime = db.Column('start_date', db.DateTime(timezone=True))
    end_datetime = db.Column('end_date', db.DateTime(timezone=True))
    start_travel_datetime = db.Column('start_travel_datetime', db.DateTime(timezone=True))
    end_travel_datetime = db.Column('end_travel_datetime', db.DateTime(timezone=True))
    created_at = db.Column('created_at',
                           db.DateTime(timezone=True),
                           default=datetime.now()
                           )
    reason = db.Column('reason', db.String())
    contact_address = db.Column('contact_address', db.String())
    contact_phone = db.Column('contact_phone', db.String())
    #TODO: travel_datetime = db.Column('travel_datetime', db.DateTime(timezone=True))
    staff = db.relationship('StaffAccount',
                            backref=db.backref('leave_requests'))
    quota = db.relationship('StaffLeaveQuota',
                            backref=db.backref('leave_requests'))

    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    country = db.Column('country', db.String())
    total_leave_days = db.Column('total_leave_days', db.Float())
    upload_file_url =  db.Column('upload_file_url', db.String())
    after_hour = db.Column("after_hour", db.Boolean())
    notify_to_line = db.Column('notify_to_line', db.Boolean(), default=False)

    @property
    def get_approved(self):
        return [a for a in self.approvals if a.is_approved]

    @property
    def get_unapproved(self):
        return [a for a in self.approvals if a.is_approved==False]

class StaffLeaveRemainQuota(db.Model):
    _tablename_ = 'staff_leave_remain_quota'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    leave_quota_id = db.Column('leave_quota_id', db.ForeignKey('staff_leave_quota.id'))
    year = db.Column('year', db.Integer())
    last_year_quota = db.Column('last_year_quota', db.Float())
    staff = db.relationship('StaffAccount',
                            backref=db.backref('remain_quota'))
    quota = db.relationship('StaffLeaveQuota', backref=db.backref('leave_quota'))


class StaffLeaveApprover(db.Model):
    __tablename__ = 'staff_leave_approvers'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    # staff account means staff under supervision
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    approver_account_id = db.Column('approver_account_id', db.ForeignKey('staff_account.id'))
    is_active = db.Column('is_active', db.Boolean(), default=True)
    requester = db.relationship('StaffAccount',
                            foreign_keys=[staff_account_id])
    account = db.relationship('StaffAccount',
                               foreign_keys=[approver_account_id])
    notified_by_line = db.Column('notified_by_line', db.Boolean(), default=True)


class StaffLeaveApproval(db.Model):
    __tablename__ = 'staff_leave_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_id = db.Column('request_id', db.ForeignKey('staff_leave_requests.id'))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_leave_approvers.id'))
    is_approved = db.Column('is_approved', db.Boolean(), default=False)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    request = db.relationship('StaffLeaveRequest', backref=db.backref('approvals'))
    approval_comment = db.Column('approval_comment', db.String())
    approver = db.relationship('StaffLeaveApprover',
                               backref=db.backref('approved_requests'))


class StaffPersonalInfoSchema(ma.ModelSchema):
    org = fields.Nested(OrgSchema)
    class Meta:
        model = StaffPersonalInfo


class StaffAccountSchema(ma.ModelSchema):
    personal_info = fields.Nested(StaffPersonalInfoSchema)


class StaffLeaveTypeSchema(ma.ModelSchema):
    class Meta:
        model = StaffLeaveType


class StaffLeaveQuotaSchema(ma.ModelSchema):
    leave_type = fields.Nested(StaffLeaveTypeSchema)
    class Meta:
        model = StaffLeaveQuota


class StaffLeaveRequestSchema(ma.ModelSchema):
    staff = fields.Nested(StaffAccountSchema)
    quota = fields.Nested(StaffLeaveQuotaSchema)
    class Meta:
        model = StaffLeaveRequest
    duration = fields.Float()


class StaffWorkFromHomeRequest(db.Model):
    __tablename__ = 'staff_work_from_home_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    start_datetime = db.Column('start_date', db.DateTime(timezone=True))
    end_datetime = db.Column('end_date', db.DateTime(timezone=True))
    created_at = db.Column('created_at',db.DateTime(timezone=True),
                           default=datetime.now())
    contact_phone = db.Column('contact_phone', db.String())
    # want to change name detail to be topic
    detail = db.Column('detail', db.String())
    deadline_date = db.Column('deadline_date', db.DateTime(timezone=True))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    staff = db.relationship('StaffAccount',
                            backref=db.backref('wfh_requests'))

    @property
    def duration(self):
        delta = self.end_datetime - self.start_datetime
        return delta.days + 1

    @property
    def get_approved(self):
        return [a for a in self.wfh_approvals if a.is_approved]

    @property
    def get_unapproved(self):
        return [a for a in self.wfh_approvals if a.is_approved == False]


class StaffWorkFromHomeJobDetail(db.Model):
    __tablename__ = 'staff_work_from_home_job_detail'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    #want to change topic to activity and activity to comment(for Approver)
    activity = db.Column('topic', db.String(), nullable=False, unique=True)
    status = db.Column('status', db.Boolean())
    wfh_id = db.Column('wfh_id', db.ForeignKey('staff_work_from_home_requests.id'))


class StaffWorkFromHomeApprover(db.Model):
    __tablename__ = 'staff_work_from_home_approvers'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    # staff account means staff under supervision
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    approver_account_id = db.Column('approver_account_id', db.ForeignKey('staff_account.id'))
    is_active = db.Column('is_active', db.Boolean(), default=True)
    requester = db.relationship('StaffAccount',
                            foreign_keys=[staff_account_id])
    account = db.relationship('StaffAccount',
                               foreign_keys=[approver_account_id])


class StaffWorkFromHomeApproval(db.Model):
    __tablename__ = 'staff_work_from_home_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_id = db.Column('request_id', db.ForeignKey('staff_work_from_home_requests.id'))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_work_from_home_approvers.id'))
    is_approved = db.Column('is_approved', db.Boolean(), default=False)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    approval_comment = db.Column('approval_comment', db.String())
    checked_at = db.Column('check_at', db.DateTime(timezone=True))
    request = db.relationship('StaffWorkFromHomeRequest', backref=db.backref('wfh_approvals'))
    approver = db.relationship('StaffWorkFromHomeApprover',
                               backref=db.backref('wfh_approved_requests'))


class StaffWorkFromHomeCheckedJob(db.Model):
    __tablename__ = 'staff_work_from_home_checked_job'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    overall_result = db.Column('overall_result', db.String())
    request_id = db.Column('request_id', db.ForeignKey('staff_work_from_home_requests.id'))
    finished_at = db.Column('finish_at', db.DateTime(timezone=True))
    request = db.relationship('StaffWorkFromHomeRequest', backref=db.backref('checked_jobs'))

    def check_comment(self, account_id):
        for approval in self.request.wfh_approvals:
            if approval.approver.account.id == account_id:
                return approval.approval_comment


class StaffWorkFromHomeRequestSchema(ma.ModelSchema):
    staff = fields.Nested(StaffAccountSchema)
    class Meta:
        model = StaffWorkFromHomeRequest
    duration = fields.Int()

