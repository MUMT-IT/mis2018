# -*- coding:utf-8 -*-

from main import db, ma
from sqlalchemy.sql import func


class Org(db.Model):
    __tablename__ = 'orgs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)
    en_name = db.Column('en_name', db.String())
    head = db.Column('head', db.String())
    parent_id = db.Column('parent_id', db.Integer, db.ForeignKey('orgs.id'))
    children = db.relationship('Org',
                               backref=db.backref('parent', remote_side=[id]))
    strategies = db.relationship('Strategy',
                                 backref=db.backref('org'))

    def __repr__(self):
        return self.name


class Strategy(db.Model):
    __tablename__ = 'strategies'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(),
                           server_default=func.now())
    content = db.Column('content', db.String(), nullable=False)
    org_id = db.Column('org_id', db.Integer(),
                       db.ForeignKey('orgs.id'), nullable=False)
    tactics = db.relationship('StrategyTactic',
                              backref=db.backref('strategy'))


class StrategyTactic(db.Model):
    __tablename__ = 'strategy_tactics'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    content = db.Column('content', db.String(), nullable=False)
    strategy_id = db.Column('strategy_id', db.Integer(),
                            db.ForeignKey('strategies.id'), nullable=False)
    themes = db.relationship('StrategyTheme',
                             backref=db.backref('tactic'))


class StrategyTheme(db.Model):
    __tablename__ = 'strategy_themes'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    content = db.Column('content', db.String(), nullable=False)
    tactic_id = db.Column('tactic_id', db.Integer(),
                          db.ForeignKey('strategy_tactics.id'), nullable=False)
    activities = db.relationship('StrategyActivity',
                                 backref=db.backref('theme'))


class StrategyActivity(db.Model):
    __tablename__ = 'strategy_activities'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    content = db.Column('content', db.String, nullable=False)
    theme_id = db.Column('theme_id', db.Integer(),
                         db.ForeignKey('strategy_themes.id'))
    kpis = db.relationship('KPI',
                           backref=db.backref('strategy_activity'))


class KPI(db.Model):
    __tablename__ = 'kpis'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    created_by = db.Column('created_by', db.String())
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(), server_default=func.now())
    updated_by = db.Column('updated_by', db.String())
    name = db.Column('name', db.String, nullable=False)
    refno = db.Column('refno', db.String())
    intent = db.Column('intent', db.String())
    frequency = db.Column('frequency', db.Integer())
    unit = db.Column('unit', db.String())
    source = db.Column('source', db.String())
    available = db.Column('available', db.Boolean())
    availability = db.Column('availability', db.String())
    formula = db.Column('formula', db.String())
    keeper = db.Column('keeper', db.String(), db.ForeignKey('staff_account.email'))
    note = db.Column('note', db.String())
    target = db.Column('target', db.String())
    target_source = db.Column('target_source', db.String())
    target_setter = db.Column('target_setter', db.String())
    target_reporter = db.Column('target_reporter', db.String())
    target_account = db.Column('target_account', db.String())
    reporter = db.Column('reporter', db.String())
    consult = db.Column('consult', db.String())
    account = db.Column('account', db.String())
    informed = db.Column('informed', db.String())
    pfm_account = db.Column('pfm_account', db.String())
    pfm_responsible = db.Column('pfm_resposible', db.String())
    pfm_consult = db.Column('pfm_consult', db.String())
    pfm_informed = db.Column('pfm_informed', db.String())
    strategy_activity_id = db.Column('strategy_activity_id',
                                     db.ForeignKey('strategy_activities.id'))
    reportlink = db.Column('reportlink', db.String())


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column('id', db.String(), primary_key=True)
    refno = db.Column('refno', db.Integer(), nullable=False)
    title = db.Column('title', db.String())
    password = db.Column('password', db.String())
    th_first_name = db.Column('th_first_name', db.String(), nullable=False)
    th_last_name = db.Column('th_last_name', db.String(), nullable=False)
    en_first_name = db.Column('en_first_name', db.String())
    en_last_name = db.Column('en_last_name', db.String())

    def __str__(self):
        return u'ID:{} {} {}'.format(self.id, self.th_first_name, self.th_last_name)


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column('id', db.Integer(), primary_key=True)
    refno = db.Column('refno', db.String(), nullable=False)
    th_class_name = db.Column('th_class_name', db.String(), nullable=False)
    en_class_name = db.Column('en_class_name', db.String(), nullable=False)
    academic_year = db.Column('academic_year', db.String(4), nullable=False)
    deadlines = db.relationship('ClassCheckIn', backref=db.backref('class'))

    def __str__(self):
        return u'{} : {}'.format(self.refno, self.academic_year)


class ClassCheckIn(db.Model):
    __tablename__ = 'class_check_in'
    id = db.Column('id', db.Integer(), primary_key=True)
    class_id = db.Column('class_id', db.ForeignKey('classes.id'))
    deadline = db.Column('deadline', db.String())
    late_mins = db.Column('late_mins', db.Integer())
    class_ = db.relationship('Class', backref=db.backref('checkin_info'))

    def __str__(self):
        return self.class_.refno


class StudentCheckInRecord(db.Model):
    __tablename__ = 'student_check_in_records'
    id = db.Column('id', db.Integer(), primary_key=True)
    stud_id = db.Column('stud_id', db.ForeignKey('students.id'))
    student = db.relationship('Student', backref=db.backref('check_in_records'))
    classchk_id = db.Column('classchk_id', db.Integer(),
                            db.ForeignKey('class_check_in.id'), nullable=False)
    classchk = db.relationship('ClassCheckIn', backref=db.backref('student_records'))
    check_in_time = db.Column('checkin', db.DateTime(timezone=True), nullable=False)
    check_in_status = db.Column('status', db.String())
    elapsed_mins = db.Column('elapsed_mins', db.Integer())


class Province(db.Model):
    __tablename__ = 'provinces'
    id = db.Column('id', db.Integer(), primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    name = db.Column('name', db.String(40), nullable=False)
    districts = db.relationship("District",
                                backref=db.backref('parent'))


class District(db.Model):
    __tablename__ = 'districts'
    id = db.Column('id', db.Integer(), primary_key=True)
    name = db.Column('name', db.String(40), nullable=False)
    code = db.Column('code', db.String(), nullable=False)
    province_id = db.Column(db.Integer(),
                            db.ForeignKey('provinces.id'))
    subdistricts = db.relationship('Subdistrict',
                                   backref=db.backref('district'))


class Subdistrict(db.Model):
    __tablename__ = 'subdistricts'
    id = db.Column('id', db.Integer(), primary_key=True)
    name = db.Column('name', db.String(80), nullable=False)
    code = db.Column('code', db.String(), nullable=False)
    district_id = db.Column(db.Integer(),
                            db.ForeignKey('districts.id'))


class KPISchema(ma.ModelSchema):
    class Meta:
        model = KPI


class HomeAddress(db.Model):
    __tablename__ = 'addresses'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    village = db.Column(db.String(), nullable=True)
    street = db.Column(db.String(), nullable=True)
    province_id = db.Column('province_id', db.Integer(),
                            db.ForeignKey('provinces.id'))
    district_id = db.Column('district_id', db.Integer(),
                            db.ForeignKey('districts.id'))
    subdistrict_id = db.Column('subdistrict_id', db.Integer(),
                               db.ForeignKey('subdistricts.id'))
    postal_code = db.Column('postal_code', db.Integer())


class Mission(db.Model):
    __tablename__ = 'missions'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)

    def __repr__(self):
        return u'{}:{}'.format(self.id, self.name)


class CostCenter(db.Model):
    __tablename__ = 'cost_centers'
    id = db.Column('id', db.String(12), primary_key=True)

    def __repr__(self):
        return u'{}'.format(self.id)


class IOCode(db.Model):
    __tablename__ = 'iocodes'
    id = db.Column('id', db.String(16), primary_key=True)
    cost_center_id = db.Column('cost_center_id', db.String(),
                               db.ForeignKey('cost_centers.id'), nullable=False)
    cost_center = db.relationship('CostCenter', backref=db.backref('iocodes'))
    mission_id = db.Column('mission_id', db.Integer(), db.ForeignKey('missions.id'), nullable=False)
    mission = db.relationship('Mission', backref=db.backref('iocodes'))
    org_id = db.Column('org_id', db.Integer(), db.ForeignKey('orgs.id'), nullable=False)
    org = db.relationship('Org', backref=db.backref('iocodes'))
    name = db.Column('name', db.String(255), nullable=False)

    def __repr__(self):
        return u'{}:{}'.format(self.id, self.name)

    def to_dict(self):
        return {
            'id': self.id,
            'costCenter': u'{}'.format(self.cost_center.id),
            'name': u'{}'.format(self.name),
            'org': u'{}'.format(self.org.name),
            'mission': u'{}'.format(self.mission.name)
        }


class OrgSchema(ma.ModelSchema):
    class Meta:
        model = Org


class Holidays(db.Model):
    __tablename__ = 'holidays'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    holiday_date = db.Column('holiday_date', db.DateTime(timezone=True))
    holiday_name = db.Column('holiday_name', db.String())

    def tojson(self):
        return {"date": self.holiday_date, "name": self.holiday_name}
