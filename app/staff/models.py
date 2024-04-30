# -*- coding:utf-8 -*-

from sqlalchemy import func

from ..main import db, ma
from werkzeug.security import generate_password_hash, check_password_hash
from dateutil.relativedelta import relativedelta
from pytz import timezone
from marshmallow import fields
from app.models import Org, OrgSchema, OrgStructure, KPI, StrategyActivity, KPICascade
from datetime import datetime

today = datetime.today()

if today.month >= 10:
    START_FISCAL_DATE = datetime(today.year, 10, 1)
    END_FISCAL_DATE = datetime(today.year + 1, 9, 30, 23, 59, 59, 0)
else:
    START_FISCAL_DATE = datetime(today.year - 1, 10, 1)
    END_FISCAL_DATE = datetime(today.year, 9, 30, 23, 59, 59, 0)

# TODO: remove hardcoded annual quota soon
LEAVE_ANNUAL_QUOTA = 10

tz = timezone('Asia/Bangkok')

staff_group_assoc_table = db.Table('staff_group_assoc',
                                   db.Column('staff_id', db.ForeignKey('staff_account.id'),
                                             primary_key=True),
                                   db.Column('group_id', db.ForeignKey('staff_special_groups.id'),
                                             primary_key=True),
                                   )

seminar_approval_attend_assoc_table = db.Table('seminar_approval_attend_assoc',
                                               db.Column('attend_id', db.ForeignKey('staff_seminar_attends.id'),
                                                         primary_key=True),
                                               db.Column('approval_id', db.ForeignKey('staff_seminar_approvals.id'),
                                                         primary_key=True),
                                               )

staff_seminar_mission_assoc_table = db.Table('staff_seminar_mission_assoc',
                                             db.Column('seminar_attend_id', db.ForeignKey('staff_seminar_attends.id')),
                                             db.Column('seminar_mission_id',
                                                       db.ForeignKey('staff_seminar_missions.id')),
                                             )

staff_seminar_objective_assoc_table = db.Table('staff_seminar_objective_assoc',
                                               db.Column('seminar_attend_id',
                                                         db.ForeignKey('staff_seminar_attends.id')),
                                               db.Column('seminar_objective_id',
                                                         db.ForeignKey('staff_seminar_objectives.id')),
                                               )

strategy_activity_staff_assoc = db.Table('strategy_activity_staff_assoc',
                                         db.Column('staff_id',
                                                   db.ForeignKey('staff_account.id'),
                                                   primary_key=True),
                                         db.Column('strategy_activity_id',
                                                   db.ForeignKey('strategy_activities.id'),
                                                   primary_key=True))


def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = u'%d/%m/%Y %H:%M'
    return dt.astimezone(bangkok).strftime(datetime_format)


# Define the Roles data model
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer(), primary_key=True)
    role_need = db.Column('role_need', db.String(), nullable=True)
    action_need = db.Column('action_need', db.String())
    resource_id = db.Column('resource_id', db.Integer())

    def to_tuple(self):
        return self.role_need, self.action_need, self.resource_id

    def __str__(self):
        return u'Role {}: can {} -> resource ID {}'.format(self.role_need, self.action_need, self.resource_id)


user_roles = db.Table('user_roles',
                      db.Column('staff_account_id', db.Integer(), db.ForeignKey('staff_account.id')),
                      db.Column('role_id', db.Integer(), db.ForeignKey('roles.id')))


class StaffAccount(db.Model):
    __tablename__ = 'staff_account'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    personal_id = db.Column('personal_id', db.ForeignKey('staff_personal_info.id'))
    email = db.Column('email', db.String(), unique=True)
    personal_info = db.relationship("StaffPersonalInfo", backref=db.backref("staff_account", uselist=False))
    line_id = db.Column('line_id', db.String(), index=True, unique=True)
    __password_hash = db.Column('password', db.String(255), nullable=True)
    customer_info_id = db.Column('customer_info_id', db.ForeignKey('staff_customer_info.id'))
    customer_info = db.relationship("StaffCustomerInfo", backref=db.backref("staff_account", cascade='all, delete-orphan'))
    roles = db.relationship('Role', secondary=user_roles, backref=db.backref('staff_account', lazy='dynamic'))
    strategy_activities = db.relationship(StrategyActivity,
                                          secondary=strategy_activity_staff_assoc,
                                          backref=db.backref('contributors'))
    kpi_cascades = db.relationship('KPICascade', backref=db.backref('staff'))

    @classmethod
    def get_account_by_email(cls, email):
        return cls.query.filter_by(email=email).first()

    @classmethod
    def get_active_accounts(cls):
        return [account for account in cls.query.all() if account.is_active]

    @property
    def fullname(self):
        return self.personal_info.fullname

    @property
    def en_fullname(self):
        return self.personal_info.en_fullname

    @property
    def has_password(self):
        return self.__password_hash != None

    @property
    def is_retired(self):
        return self.personal_info.retired is True

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
        return str(self.id)

    def __str__(self):
        return u'{}'.format(self.email)

    @property
    def total_wfh_duration(self):
        return sum([wfh.duration for wfh in self.wfh_requests if not wfh.cancelled_at and wfh.get_approved])

    @property
    def new_invitations(self):
        return self.invitations.filter_by(response=None).all()

    @property
    def pending_invitations(self):
        return self.invitations.filter_by(response='ไม่แน่ใจ').all()


class StaffPersonalInfo(db.Model):
    __tablename__ = 'staff_personal_info'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    en_title = db.Column('en_title', db.String())
    th_title = db.Column('th_title', db.String())
    en_firstname = db.Column('en_firstname', db.String(), nullable=False)
    en_lastname = db.Column('en_lastname', db.String(), nullable=False)
    th_firstname = db.Column('th_firstname', db.String(), nullable=True)
    th_lastname = db.Column('th_lastname', db.String(), nullable=True)
    org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('staff'))
    employed_date = db.Column('employed_date', db.Date(), nullable=True)
    employment_id = db.Column('employment_id',
                              db.ForeignKey('staff_employments.id'))
    employment = db.relationship('StaffEmployment',
                                 backref=db.backref('staff'))
    finger_scan_id = db.Column('finger_scan_id', db.Integer)
    academic_staff = db.Column('academic_staff', db.Boolean())
    retired = db.Column('retired', db.Boolean(), default=False)
    job_position_id = db.Column(db.ForeignKey('staff_job_positions.id'))
    job_position = db.relationship('StaffJobPosition',
                                   backref=db.backref('job_position_staff'))
    position = db.Column('position', db.String(), info={'label': u'ตำแหน่ง'})
    mobile_phone = db.Column('mobile_phone', db.String(), info={'label': u'มือถือ'})
    telephone = db.Column('telephone', db.String(), info={'label': u'โทร'})
    retirement_date = db.Column('retirement_date', db.Date(), nullable=True)
    resignation_date = db.Column('resignation_date', db.Date(), nullable=True)

    def __str__(self):
        return self.fullname

    @property
    def fullname(self):
        try:
            academic_position = self.academic_positions[0]
        except IndexError:
            if self.academic_staff:
                th_position = u'อ.'
                en_position = u'Lect.'
            else:
                th_position = None
                en_position = None
        else:
            th_position = academic_position.position.shortname_th
            en_position = academic_position.position.shortname_en

        if self.th_firstname or self.th_lastname:
            if th_position:
                if self.th_title == u'ดร.':
                    return u'{} {}{} {}'.format(th_position, self.th_title or '', self.th_firstname, self.th_lastname)
                else:
                    return u'{} {} {}'.format(th_position, self.th_firstname, self.th_lastname)
            else:
                return u'{}{} {}'.format(self.th_title or '', self.th_firstname, self.th_lastname)
        else:
            if en_position:
                if self.en_title == u'Dr.':
                    return u'{} {}{} {}'.format(en_position,
                                                self.en_title or '',
                                                self.en_firstname,
                                                self.en_lastname)
                else:
                    return u'{} {} {}'.format(en_position, self.en_firstname, self.en_lastname)
            else:
                return u'{}{} {}'.format(self.en_title or '', self.en_firstname, self.en_lastname)

    @property
    def en_fullname(self):
        try:
            academic_position = self.academic_positions[0]
        except IndexError:
            if self.academic_staff:
                en_position = u'Lecturer'
            else:
                en_position = None
        else:
            en_position = academic_position.position.shortname_en

        if en_position:
            if self.en_title == u'Dr.':
                return u'{} {}{} {}'.format(en_position,
                                            self.en_title,
                                            self.en_firstname,
                                            self.en_lastname)
            else:
                return u'{} {} {}'.format(en_position, self.en_firstname, self.en_lastname)
        else:
            if self.en_title == u'Dr.':
                return u'{}{} {}'.format(self.en_title, self.en_firstname, self.en_lastname)
            else:
                return u'{}{} {}'.format(self.en_title or '', self.en_firstname, self.en_lastname)

    def get_employ_period(self):
        today = datetime.now().date()
        period = relativedelta(today, self.employed_date)
        return period

    def get_employ_period_of_current_fiscal_year(self):
        period = relativedelta(START_FISCAL_DATE, self.employed_date)
        return period

    @property
    def is_eligible_for_leave(self, minmonth=6.0):
        period = self.get_employ_period()
        if period.years > 0:
            return True
        elif period.years == 0 and period.months >= minmonth:
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
        # return len([req for req in self.staff_account.leave_requests if req.quota_id == leave_quota_id])

    def get_total_pending_leaves_request(self, leave_quota_id, start_date=None, end_date=None):
        total_leaves = []
        for req in self.staff_account.leave_requests:
            if req.quota.id == leave_quota_id:
                if start_date is None or end_date is None and not req.cancelled_at \
                        and not req.get_approved and not req.get_unapproved:
                    total_leaves.append(req.total_leave_days)
                else:
                    if req.start_datetime >= start_date and req.end_datetime <= end_date \
                            and not req.cancelled_at and not req.get_approved and not req.get_unapproved:
                        total_leaves.append(req.total_leave_days)

        return sum(total_leaves)

    def get_remaining_leave_day(self, leave_quota_id):
        if not self.employment:
            remain_days = 0
            return remain_days
        year = START_FISCAL_DATE.year - 1
        last_year = StaffLeaveRemainQuota.query.filter_by(leave_quota_id=leave_quota_id, year=year).first()
        if last_year:
            last_year_quota = last_year.last_year_quota
        else:
            last_year_quota = 0
        delta = self.get_employ_period()
        leave_quota = StaffLeaveQuota.query.get(leave_quota_id)
        max_cum_quota = self.get_max_cum_quota_per_year(leave_quota)
        if delta.years > 0:
            if max_cum_quota:
                before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            elif leave_quota.max_per_year:
                quota_limit = leave_quota.max_per_year
            else:
                quota_limit = 0
        else:
            if leave_quota.first_year:
                quota_limit = leave_quota.first_year
            else:
                quota_limit = 0
        remain = quota_limit - self.get_total_leaves(leave_quota_id)
        if remain < 0:
            remain = 0
        return remain


class StaffCustomerInfo(db.Model):
    __tablename__ = 'staff_customer_info'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), info={'label': 'คำนำหน้า', 'choices': [('None', 'กรุณาเลือกคำนำหน้า'),
                                                                                   ('นาย', 'นาย'),
                                                                                   ('นาง', 'นาง'),
                                                                                   ('นางสาว', 'นางสาว')
                                                                                 ]})
    firstname = db.Column('firstname', db.String(), nullable=False ,info={'label': 'ชื่อ'})
    lastname = db.Column('lastname', db.String(), nullable=False ,info={'label': 'นามสกุล'})
    organization_name = db.Column('organization_name', db.String() ,info={'label': 'บริษัท'})
    taxpayer_identification_no = db.Column('taxpayer_identification_no', db.String() ,info={'label': 'เลขประจำตัวผู้เสียภาษีอากร'})
    address = db.Column('address', db.Text() ,info={'label': 'ที่อยู่'})
    telephone = db.Column('telephone', db.String() ,info={'label': 'เบอร์โทรศัพท์'})

    def __str__(self):
        return self.fullname

    @property
    def fullname(self):
        return '{} {} {}'.format(self.title, self.firstname, self.lastname)


class StaffEduDegree(db.Model):
    __tablename__ = 'staff_edu_degree'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    level = db.Column('level', db.String(), nullable=False,
                      info={'label': u'ระดับ',
                            'choices': [('undergraduate', u'ต่ำกว่าปริญญาตรี'),
                                        ('bachelor', u'ปริญญาตรี'),
                                        ('master', u'ปริญญาโท'),
                                        ('doctorate', u'ปริญญาเอก')]
                            })
    en_title = db.Column('en_title', db.String(), info={'label': u'Title'})
    th_title = db.Column('th_title', db.String(), info={'label': u'ชื่อปริญญา'})
    en_major = db.Column('en_major', db.String(), info={'label': u'Major'})
    th_major = db.Column('th_major', db.String(), info={'label': u'สาขา'})
    en_school = db.Column('en_school', db.String(), info={'label': u'ชื่อสถาบัน'})
    th_country = db.Column('th_country', db.String(), info={'label': u'ประเทศ'})
    received_date = db.Column(db.Date(), info={'label': u'ปีที่จบการศึกษา'})
    personal_info_id = db.Column(db.ForeignKey('staff_personal_info.id'))
    personal_info = db.relationship(StaffPersonalInfo,
                                    backref=db.backref('degrees',
                                                       order_by='StaffEduDegree.received_date.desc()'))


class StaffAcademicPosition(db.Model):
    __tablename__ = 'staff_academic_position'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    fullname_th = db.Column('fullname_th', db.String(), nullable=False)
    shortname_th = db.Column('shortname_th', db.String(), nullable=False)
    fullname_en = db.Column('fullname_en', db.String(), nullable=False)
    shortname_en = db.Column('shortname_en', db.String(), nullable=False)
    level = db.Column('level', db.Integer(), nullable=False,
                      info={'label': u'',
                            'choices': ((0, u'อาจารย์'),
                                        (1, u'ผู้ช่วยศาสตราจารย์'),
                                        (2, u'รองศาสตราจารย์'),
                                        (3, u'ศาสตราจารย์'))
                            })

    def __str__(self):
        return self.shortname_th


class StaffAcademicPositionRecord(db.Model):
    __tablename__ = 'staff_academic_position_records'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    personal_info_id = db.Column(db.ForeignKey('staff_personal_info.id'))
    personal_info = db.relationship(StaffPersonalInfo,
                                    backref=db.backref('academic_positions',
                                                       order_by='StaffAcademicPositionRecord.appointed_at.desc()'))
    appointed_at = db.Column(db.Date(), info={'label': u'แต่งตั้งเมื่อ'})
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    position_id = db.Column(db.ForeignKey('staff_academic_position.id'))
    position = db.relationship(StaffAcademicPosition, backref=db.backref('records'))

    def __str__(self):
        return self.position.fullname_th


class StaffEmployment(db.Model):
    __tablename__ = 'staff_employments'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), unique=True, nullable=False)

    def __str__(self):
        return self.title


class StaffJobPosition(db.Model):
    __tablename__ = 'staff_job_positions'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    en_title = db.Column('en_title', db.String())
    th_title = db.Column('th_title', db.String())

    def __str__(self):
        return self.th_title


class StaffSpecialGroup(db.Model):
    __tablename__ = 'staff_special_groups'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), unique=True, nullable=False)
    group_code = db.Column('group_code', db.String(), unique=True, nullable=False)
    staffs = db.relationship('StaffAccount', backref=db.backref('groups'),
                             secondary=staff_group_assoc_table)


class StaffHeadPosition(db.Model):
    __tablename__ = 'staff_head_positions'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    position = db.Column('position', db.String(), nullable=False)
    org_id = db.Column('org_id', db.Integer(), db.ForeignKey('orgs.id'))
    org_structure_id = db.Column('org_structure_id', db.Integer(), db.ForeignKey('org_structure.id'))
    org = db.relationship(Org, backref=db.backref('head_position_org'))
    org_structure = db.relationship(OrgStructure, backref=db.backref('head_position_org_structure'))
    staff = db.relationship('StaffAccount', backref=db.backref('head_position_staff'))


class StaffLeaveType(db.Model):
    __tablename__ = 'staff_leave_types'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    type_ = db.Column('type', db.String(), nullable=False, unique=True)
    request_in_advance = db.Column('request_in_advance', db.Boolean())
    document_required = db.Column('document_required', db.Boolean(), default=False)
    reason_required = db.Column('reason_required', db.Boolean())
    requester_self_added = db.Column('requester_self_added', db.Boolean())

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


class StaffLeaveUsedQuota(db.Model):
    __tablename__ = 'staff_leave_used_quota'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    leave_type_id = db.Column('leave_type_id', db.ForeignKey('staff_leave_types.id'))
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    fiscal_year = db.Column('fiscal_year', db.Integer())
    used_days = db.Column('used_days', db.Float())
    pending_days = db.Column('pending_days', db.Float(), default=0)
    quota_days = db.Column('quota_days', db.Float())
    staff = db.relationship('StaffAccount', backref=db.backref('leave_used_quota', lazy='dynamic'),
                            foreign_keys=[staff_account_id])
    leave_type = db.relationship('StaffLeaveType', backref=db.backref('type_used_quota'))


class StaffLeaveRequest(db.Model):
    __tablename__ = 'staff_leave_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    leave_quota_id = db.Column('quota_id', db.ForeignKey('staff_leave_quota.id'))
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    # TODO: fixed offset-naive and offset-timezone comparison error.
    start_datetime = db.Column('start_date', db.DateTime(timezone=True))
    end_datetime = db.Column('end_date', db.DateTime(timezone=True))
    start_travel_datetime = db.Column('start_travel_datetime', db.DateTime(timezone=True))
    end_travel_datetime = db.Column('end_travel_datetime', db.DateTime(timezone=True))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    reason = db.Column('reason', db.String())
    contact_address = db.Column('contact_address', db.String())
    contact_phone = db.Column('contact_phone', db.String())
    # TODO: travel_datetime = db.Column('travel_datetime', db.DateTime(timezone=True))
    staff = db.relationship('StaffAccount', backref=db.backref('leave_requests'), foreign_keys=[staff_account_id])
    quota = db.relationship('StaffLeaveQuota', backref=db.backref('leave_requests'))

    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    cancelled_account_id = db.Column('cancelled_account_id', db.ForeignKey('staff_account.id'))
    country = db.Column('country', db.String())
    total_leave_days = db.Column('total_leave_days', db.Float())
    upload_file_url = db.Column('upload_file_url', db.String())
    after_hour = db.Column("after_hour", db.Boolean())
    notify_to_line = db.Column('notify_to_line', db.Boolean(), default=False)
    cancelled_by = db.relationship('StaffAccount', foreign_keys=[cancelled_account_id])
    last_cancel_requested_at = db.Column('last_cancel_requested_at', db.DateTime(timezone=True))

    def get_approved_by(self, approver):
        return [a for a in self.approvals if a.approver.account == approver]

    @property
    def get_approved(self):
        return [a for a in self.approvals if a.is_approved]

    @property
    def get_unapproved(self):
        return [a for a in self.approvals if a.is_approved is False]

    def __str__(self):
        return "{}: {}".format(self.id, self.staff.email)

    @property
    def get_last_cancel_request_from_now(self):
        if self.last_cancel_requested_at:
            delta = datetime.now(tz) - self.last_cancel_requested_at
            days = delta.days
        else:
            days = 0
        return days


class StaffLeaveRemainQuota(db.Model):
    _tablename_ = 'staff_leave_remain_quota'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    leave_quota_id = db.Column('leave_quota_id', db.ForeignKey('staff_leave_quota.id'))
    year = db.Column('year', db.Integer())
    last_year_quota = db.Column('last_year_quota', db.Float())
    staff = db.relationship('StaffAccount',
                            backref=db.backref('remain_quota', uselist=False))
    quota = db.relationship('StaffLeaveQuota', backref=db.backref('leave_quota'))


class StaffLeaveApprover(db.Model):
    __tablename__ = 'staff_leave_approvers'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    # staff account means staff under supervision
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    approver_account_id = db.Column('approver_account_id', db.ForeignKey('staff_account.id'))
    is_active = db.Column('is_active', db.Boolean(), default=True)
    requester = db.relationship('StaffAccount',
                                backref=db.backref('leave_requesters'),
                                foreign_keys=[staff_account_id])
    account = db.relationship('StaffAccount',
                              backref=db.backref('leave_approvers'),
                              foreign_keys=[approver_account_id])
    notified_by_line = db.Column('notified_by_line', db.Boolean(), default=True)

    @property
    def approver_name(self):
        return self.account.personal_info.fullname

    def __str__(self):
        return "{}->{}".format(self.account.email, self.requester.email)


class StaffLeaveApproval(db.Model):
    __tablename__ = 'staff_leave_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_id = db.Column('request_id', db.ForeignKey('staff_leave_requests.id'))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_leave_approvers.id'))
    is_approved = db.Column('is_approved', db.Boolean(), default=False)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    request = db.relationship('StaffLeaveRequest',
                              backref=db.backref('approvals', cascade='all, delete-orphan'))
    approval_comment = db.Column('approval_comment', db.String())
    approver = db.relationship('StaffLeaveApprover',
                               backref=db.backref('approved_requests'))


class StaffPersonalInfoSchema(ma.SQLAlchemyAutoSchema):
    org = fields.Nested(OrgSchema)

    class Meta:
        model = StaffPersonalInfo


class StaffAccountSchema(ma.SQLAlchemyAutoSchema):
    personal_info = fields.Nested(StaffPersonalInfoSchema)


class StaffLeaveTypeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = StaffLeaveType


class StaffLeaveQuotaSchema(ma.SQLAlchemyAutoSchema):
    leave_type = fields.Nested(StaffLeaveTypeSchema)

    class Meta:
        model = StaffLeaveQuota


class StaffLeaveRequestSchema(ma.SQLAlchemyAutoSchema):
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
    created_at = db.Column('created_at', db.DateTime(timezone=True),
                           default=datetime.now())
    contact_phone = db.Column('contact_phone', db.String())
    # want to change name detail to be topic
    detail = db.Column('detail', db.String())
    deadline_date = db.Column('deadline_date', db.DateTime(timezone=True))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    staff = db.relationship('StaffAccount', backref=db.backref('wfh_requests'))
    notify_to_line = db.Column('notify_to_line', db.Boolean(), default=False)

    def get_approved_by(self, approver):
        return [a for a in self.wfh_approvals if a.approver.account == approver]

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
    # want to change topic to activity and activity to comment(for Approver)
    activity = db.Column('topic', db.String(), nullable=False, unique=False)
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
                                backref=db.backref('wfh_requesters'),
                                foreign_keys=[staff_account_id])
    account = db.relationship('StaffAccount',
                              backref=db.backref('wfh_approvers'),
                              foreign_keys=[approver_account_id])
    notified_by_line = db.Column('notified_by_line', db.Boolean(), default=True)


class StaffWorkFromHomeApproval(db.Model):
    __tablename__ = 'staff_work_from_home_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_id = db.Column('request_id', db.ForeignKey('staff_work_from_home_requests.id'))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_work_from_home_approvers.id'))
    is_approved = db.Column('is_approved', db.Boolean(), default=False)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    approval_comment = db.Column('approval_comment', db.String())
    request = db.relationship('StaffWorkFromHomeRequest',
                              backref=db.backref('wfh_approvals', cascade='all, delete-orphan'))
    approver = db.relationship('StaffWorkFromHomeApprover',
                               backref=db.backref('wfh_approved_requests'))


class StaffWorkFromHomeCheckedJob(db.Model):
    __tablename__ = 'staff_work_from_home_checked_job'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    overall_result = db.Column('overall_result', db.String())
    request_id = db.Column('request_id', db.ForeignKey('staff_work_from_home_requests.id'))
    finished_at = db.Column('finish_at', db.DateTime(timezone=True))
    request = db.relationship('StaffWorkFromHomeRequest',
                              backref=db.backref('checked_jobs', cascade='all, delete-orphan'))

    def check_comment(self, account_id):
        for approval in self.request.wfh_approvals:
            if approval.approver.account.id == account_id:
                return approval.approval_comment


class StaffWorkFromHomeRequestSchema(ma.SQLAlchemyAutoSchema):
    staff = fields.Nested(StaffAccountSchema)

    class Meta:
        model = StaffWorkFromHomeRequest

    duration = fields.Int()


class StaffSeminar(db.Model):
    __tablename__ = 'staff_seminar'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    start_datetime = db.Column('start_date', db.DateTime(timezone=True), info={'label': u'วันเริ่มต้น'})
    end_datetime = db.Column('end_date', db.DateTime(timezone=True), info={'label': u'วันสิ้นสุด'})
    created_at = db.Column('created_at', db.DateTime(timezone=True),
                           default=datetime.now())
    topic_type = db.Column('topic_type', db.String(),
                           info={'label': u'ประเภท',
                                 'choices': [(c, c) for c in [u'อบรม', u'สัมมนา', u'ประชุม', u'ประชุมวิชาการ']]})
    topic = db.Column('topic', db.String(), info={'label': u'หัวข้อ'})
    organize_by = db.Column('organize_by', db.String(), info={'label': u'หน่วยงานที่จัด'})
    location = db.Column('location', db.String(), info={'label': u'สถานที่จัด'})
    is_online = db.Column('is_online', db.Boolean(), default=False, info={'label': u'จัดแบบ Online'})
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    upload_file_url = db.Column('upload_file_url', db.String())

    def __str__(self):
        return u'{}'.format(self.topic)


class StaffSeminarMission(db.Model):
    __tablename__ = 'staff_seminar_missions'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    mission = db.Column('mission', db.String())


class StaffSeminarObjective(db.Model):
    __tablename__ = 'staff_seminar_objectives'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    objective = db.Column('objective', db.String())


class StaffSeminarAttend(db.Model):
    __tablename__ = 'staff_seminar_attends'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    seminar_id = db.Column('seminar_id', db.ForeignKey('staff_seminar.id'))
    start_datetime = db.Column('start_date', db.DateTime(timezone=True), info={'label': u'วันเริ่มต้น'})
    end_datetime = db.Column('end_date', db.DateTime(timezone=True), info={'label': u'วันสิ้นสุด'})
    created_at = db.Column('created_at', db.DateTime(timezone=True),
                           default=datetime.now())
    role = db.Column('role', db.String(), info={'label': u'บทบาท', 'choices': [
        (c, c) for c in [u'ผู้เข้าร่วม', u'อาจารย์พิเศษ', u'วิทยากร', u'ที่ปรึกษา', u'กรรมการ', u'นิเทศน์งาน']]})
    registration_fee = db.Column('registration_fee', db.Float(), info={'label': u'ค่าลงทะเบียน (บาท)'})
    invited_document_id = db.Column('document_id', db.String(), info={'label': u'เลขที่หนังสือเชิญ'})
    invited_organization = db.Column('invited_organization', db.String(), info={'label': u'หน่วยงานที่เชิญ'})
    invited_document_date = db.Column('invited_document_date', db.DateTime(timezone=True),
                                      info={'label': u'ลงวันที่หนังสือ'})
    document_title = db.Column('document_title', db.String(), info={'label': u'ชื่อเรื่องหนังสือ'})
    taxi_cost = db.Column('taxi_cost', db.Float(), info={'label': u'ค่า Taxi (บาท)'})
    train_ticket_cost = db.Column('train_ticket_cost', db.Float(), info={'label': u'ค่าตั๋วรถไฟ (บาท)'})
    flight_ticket_cost = db.Column('flight_ticket_cost', db.Float(), info={'label': u'ค่าตั๋วเครื่องบิน (บาท)'})
    fuel_cost = db.Column('fuel_cost', db.Float(), info={'label': u'ค่าน้ำมัน (บาท)'})
    accommodation_cost = db.Column('accommodation_cost', db.Float(), info={'label': u'ค่าที่พัก (บาท)'})
    budget_type = db.Column('budget_type', db.String(), info={'label': u'แหล่งทุน'})
    transaction_fee = db.Column('transaction_fee', db.Float(), info={'label': u'ค่าธรรมเนียมการโอน (บาท)'})
    budget = db.Column('budget', db.Float(), info={'label': u'ค่าใช้จ่ายรวมทั้งหมด (บาท)'})
    attend_online = db.Column('attend_online', db.Boolean(), default=False,
                              info={'label': u'เข้าร่วมผ่านช่องทาง online'})
    middle_level_approver_account_id = db.Column('middle_level_approver_account_id', db.ForeignKey('staff_account.id'))
    middle_level_approver = db.relationship('StaffAccount', foreign_keys=[middle_level_approver_account_id],
                                            backref=db.backref('seminar_middle_approver_attends', lazy='dynamic'))
    lower_level_approver_account_id = db.Column('lower_level_approver_account_id', db.ForeignKey('staff_account.id'))
    lower_level_approver = db.relationship('StaffAccount', foreign_keys=[lower_level_approver_account_id],
                                           backref=db.backref('seminar_lower_approver_attends', lazy='dynamic'))
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    document_no = db.Column('document_no', db.String())
    staff = db.relationship('StaffAccount', foreign_keys=[staff_account_id],
                            backref=db.backref('seminar_attends', lazy='dynamic'))
    seminar = db.relationship('StaffSeminar', backref=db.backref('attends'), foreign_keys=[seminar_id])
    objectives = db.relationship('StaffSeminarObjective', secondary=staff_seminar_objective_assoc_table,
                                 backref=db.backref('objective_attends'))
    missions = db.relationship('StaffSeminarMission', secondary=staff_seminar_mission_assoc_table,
                               backref=db.backref('mission_attends'))

    def __str__(self):
        return u'{}'.format(self.seminar)

    def is_approved_by(self, user):
        return self.proposal.filter_by(proposer=user).first()

    @property
    def mission_list(self):
        return [m.mission for m in self.missions]

    @property
    def objective_list(self):
        return [o.objective for o in self.objectives]


class StaffSeminarProposal(db.Model):
    __tablename__ = 'staff_seminar_proposals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    seminar_attend_id = db.Column('seminar_attend_id', db.ForeignKey('staff_seminar_attends.id'))
    seminar_attend = db.relationship('StaffSeminarAttend', foreign_keys=[seminar_attend_id],
                                     backref=db.backref('proposal', lazy='dynamic'))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    is_approved = db.Column('is_approved', db.Boolean(), default=True)
    comment = db.Column('approval_comment', db.String())
    proposer_account_id = db.Column('proposer_account_id', db.ForeignKey('staff_account.id'))
    proposer = db.relationship('StaffAccount', foreign_keys=[proposer_account_id],
                               backref=db.backref('seminar_proposer', lazy='dynamic'))
    previous_proposal_id = db.Column('previous_proposal_id', db.Integer())
    upload_file_url = db.Column('upload_file_url', db.String())
    proposer_head_position_id = db.Column('proposer_head_position_id', db.ForeignKey('staff_head_positions.id'))
    head_position = db.relationship('StaffHeadPosition', foreign_keys=[proposer_head_position_id],
                                    backref=db.backref('proposer_head_position'))


class StaffSeminarDocument(db.Model):
    __tablename__ = 'staff_seminar_documents'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    seminar_proposal_id = db.Column('seminar_proposal_id', db.ForeignKey('staff_seminar_proposals.id'))
    proposal = db.relationship('StaffSeminarProposal', backref=db.backref('seminar_document')
                               , foreign_keys=[seminar_proposal_id])
    document_no = db.Column('document_no', db.String)
    # doc_internal_sending_id = db.Column('doc_internal_sending_id', db.ForeignKey('doc_internal_sending.id'))


class StaffSeminarApproval(db.Model):
    __tablename__ = 'staff_seminar_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    seminar_attend_id = db.Column('seminar_attend_id', db.ForeignKey('staff_seminar_attends.id'))
    seminar_attend = db.relationship('StaffSeminarAttend', backref=db.backref('seminar_approval')
                                     , foreign_keys=[seminar_attend_id])
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    is_approved = db.Column('is_approved', db.Boolean(), default=True)
    approval_comment = db.Column('approval_comment', db.String())
    final_approver_account_id = db.Column('final_approver_account_id', db.ForeignKey('staff_account.id'))
    recorded_account_id = db.Column('recorded_account_id', db.ForeignKey('staff_account.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True),
                           default=datetime.now())
    approver = db.relationship('StaffAccount', backref=db.backref('approval_approver'),
                               foreign_keys=[final_approver_account_id])
    recorded_by = db.relationship('StaffAccount', backref=db.backref('approval_recorded_by'),
                                  foreign_keys=[recorded_account_id])
    attend = db.relationship('StaffSeminarAttend',
                             secondary=seminar_approval_attend_assoc_table,
                             backref=db.backref('seminar_approval_attendee', lazy='dynamic'))


class StaffWorkLogin(db.Model):
    __tablename__ = 'staff_work_logins'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    date_id = db.Column('date_id', db.String())
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship('StaffAccount', backref=db.backref('work_logins', lazy='dynamic'))
    start_datetime = db.Column('start_datetime', db.DateTime(timezone=True))
    end_datetime = db.Column('end_datetime', db.DateTime(timezone=True))
    checkin_mins = db.Column('checkin_mins', db.Integer())
    checkout_mins = db.Column('checkout_mins', db.Integer())
    num_scans = db.Column('num_scans', db.Integer(), default=0)
    qrcode_in_exp_datetime = db.Column('qrcode_in_exp_datetime', db.DateTime(timezone=True))
    qrcode_out_exp_datetime = db.Column('qrcode_out_exp_datetime', db.DateTime(timezone=True))
    lat = db.Column('lat', db.Numeric())
    long = db.Column('long', db.Numeric())

    @staticmethod
    def generate_date_id(date):
        return date.strftime('%Y%m%d')


class StaffRequestWorkLogin(db.Model):
    __tablename__ = 'staff_request_work_logins'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship('StaffAccount', backref=db.backref('request_work_logins', lazy='dynamic'),
                            foreign_keys=[staff_account_id])
    reason = db.Column('reason', db.String())
    requested_at = db.Column('requested_at', db.DateTime(timezone=True))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship('StaffAccount', backref=db.backref('approver_work_logins', lazy='dynamic'),
                               foreign_keys=[approver_id])
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    date_id = db.Column('date_id', db.String())
    work_datetime = db.Column('work_datetime', db.DateTime(timezone=True))
    is_checkin = db.Column('is_checkin', db.Boolean(), default=True)

    @staticmethod
    def generate_date_id(date):
        return date.strftime('%Y%m%d')


class StaffShiftSchedule(db.Model):
    __tablename__ = 'staff_shift_schedule'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship('StaffAccount', backref=db.backref('shift_schedule'))
    start_datetime = db.Column('start_datetime', db.DateTime(timezone=True))
    end_datetime = db.Column('end_datetime', db.DateTime(timezone=True))
    detail = db.Column('detail', db.String())
    abbr = db.Column('abbr', db.String())


class StaffShiftRole(db.Model):
    __tablename__ = 'staff_shift_role'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    role = db.Column('role', db.String())
    org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('shift_role'))

    def __str__(self):
        return self.role


class KPIStaffAssociation(db.Model):
    __tablename__ = 'kpi_staff_association'
    kpi_id = db.Column(db.Integer, db.ForeignKey('kpis.id'), primary_key=True)
    staff_account_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), primary_key=True)
    ratio = db.Column(db.String())
    comment = db.Column(db.String())
    staff = db.relationship('StaffAccount', backref=db.backref('delegated_kpis'))
    kpi = db.relationship('KPI', backref=db.backref('staff'))


# class StaffSapNo(db.Model):
#     __tablename__ = 'staff_sap_no'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     sap_no = db.Column('sap_no', db.Integer)
#     staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
#     created_at = db.Column('created_at',db.DateTime(timezone=True),
#                            default=datetime.now())
#     cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))


class StaffGroupAssociation(db.Model):
    __tablename__ = 'staff_group_associations'
    group_detail_id = db.Column(db.ForeignKey('staff_group_details.id'), primary_key=True)
    group_detail = db.relationship('StaffGroupDetail',
                                   backref=db.backref('group_members', cascade='all, delete-orphan'))
    staff_id = db.Column(db.ForeignKey('staff_account.id'), primary_key=True)
    staff = db.relationship(StaffAccount, backref=db.backref('teams'))
    position_id = db.Column(db.ForeignKey('staff_group_positions.id'), primary_key=True)
    position = db.relationship('StaffGroupPosition', backref=db.backref('group_members'))


class StaffGroupDetail(db.Model):
    __tablename__ = 'staff_group_details'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    activity_name = db.Column('activity_name', db.String(), nullable=False, info={'label': 'ชื่อกลุ่ม'})
    appointment_date = db.Column('appointment_date', db.Date(), nullable=True, info={'label': 'วันที่แต่งตั้ง'})
    expiration_date = db.Column('expiration_date', db.Date(), nullable=True, info={'label': 'วันที่หมดวาระ'})
    responsibility = db.Column('responsibility', db.Text(), info={'label': 'หน้าที่ความรับผิดชอบ'})
    public = db.Column('public', db.Boolean(), default=False, info={'label': 'เปิดเผย'})
    official = db.Column('official', db.Boolean(), default=False, info={'label': 'ไม่เปิดเผย'})
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('group_committee'))

    def buddhist_year(self):
        return u'{}'.format(self.appointment_date.year + 543)

    def __str__(self):
        return f'{self.activity_name}'


class StaffGroupPosition(db.Model):
    __tablename__ = 'staff_group_positions'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    position = db.Column('position', db.String(), nullable=False, info={'label': 'ตำแหน่ง'})

    def __str__(self):
        return f'{self.position}'
