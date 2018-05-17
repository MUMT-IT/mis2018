from main import db, ma
from sqlalchemy.sql import func

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    email = db.Column('email', db.String(), nullable=False)
    username = db.Column('username', db.String(), nullable=False, unique=True)


class Org(db.Model):
    __tablename__ = 'orgs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)
    head = db.Column('head', db.String())
    parent_id = db.Column('parent_id', db.Integer, db.ForeignKey('orgs.id'))
    children = db.relationship('Org',
                    backref=db.backref('parent', remote_side=[id]))
    strategies = db.relationship('Strategy',
                    backref=db.backref('org'))


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
    keeper = db.Column('keeper', db.String(), db.ForeignKey('users.username'))
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
    th_first_name = db.Column('th_first_name', db.String(), nullable=False)
    th_last_name = db.Column('th_last_name', db.String(), nullable=False)
    en_first_name = db.Column('en_first_name', db.String())
    en_last_name = db.Column('en_last_name', db.String())
    class_check_ins = db.relationship('StudentCheckInRecord',
                        backref=db.backref('student'))


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column('id', db.Integer(), primary_key=True)
    refno = db.Column('refno', db.String(), nullable=False)
    th_class_name = db.Column('th_class_name', db.String(), nullable=False)
    en_class_name = db.Column('en_class_name', db.String(), nullable=False)
    academic_year = db.Column('academic_year', db.String(4), nullable=False)
    deadlines = db.relationship('ClassCheckIn', backref=db.backref('class'))


class ClassCheckIn(db.Model):
    __tablename__ = 'class_check_in'
    id = db.Column('id', db.Integer(), primary_key=True)
    class_id = db.Column('class_id', db.ForeignKey('classes.id'))
    deadline = db.Column('deadline', db.String())
    late_mins = db.Column('late_mins', db.Integer())


class StudentCheckInRecord(db.Model):
    __tablename__ = 'student_check_in_records'
    id = db.Column('id', db.Integer(), primary_key=True)
    stud_id = db.Column('stud_id', db.ForeignKey('students.id'))
    classchk_id = db.Column('classchk_id', db.Integer(),
                    db.ForeignKey('class_check_in.id'), nullable=False)
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