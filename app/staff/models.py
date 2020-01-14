from ..main import db
from werkzeug import generate_password_hash, check_password_hash
from datetime import datetime


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

    def __str__(self):
        return u'{} {}'.format(self.en_firstname, self.en_lastname)


    def get_employ_period(self):
        today = datetime.now().date()
        period = today - self.employed_date
        return period.days

    @property
    def is_eligible_for_leave(self, minmonth=6.0):
        return (self.get_employ_period()/12.0) > minmonth


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


class StaffLeaveType(db.Model):
    __tablename__ = 'staff_leave_types'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    type_ = db.Column('type', db.String(), nullable=False, unique=True)


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


class StaffLeaveRequest(db.Model):
    __tablename__ = 'staff_leave_requests'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    leave_quota_id = db.Column('quota_id', db.ForeignKey('staff_leave_quota.id'))
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    start_datetime = db.Column('start_date', db.DateTime(timezone=True))
    end_datetime = db.Column('end_date', db.DateTime(timezone=True))
    created_at = db.Column('created_at',
                           db.DateTime(timezone=True),
                           default=datetime.utcnow()
                           )
    reason = db.Column('reason', db.String())
    contact_address = db.Column('contact_address', db.String())
    contact_phone = db.Column('contact_phone', db.String())


class StaffLeaveApprover(db.Model):
    __tablename__ = 'staff_leave_approvers'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    approver_account_id = db.Column('approver_account_id', db.ForeignKey('staff_account.id'))
    is_active = db.Column('is_active', db.Boolean(), default=True)


class StaffLeaveApproval(db.Model):
    __tablename__ = 'staff_leave_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    request_id = db.Column('request_id', db.ForeignKey('staff_leave_requests.id'))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_leave_approvers.id'))
    is_approved = db.Column('is_approved', db.Boolean(), default=False)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    request  = db.relationship('StaffLeaveRequest', backref=db.backref('approvals'))
