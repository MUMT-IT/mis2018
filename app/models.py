# -*- coding:utf-8 -*-
import textwrap
from app.main import db, ma
from sqlalchemy.sql import func

dataset_tag_assoc = db.Table('db_dataset_tag_assoc',
                             db.Column('dataset_id', db.ForeignKey('db_datasets.id'), primary_key=True),
                             db.Column('tag_id', db.ForeignKey('db_datatags.id'), primary_key=True)
                             )


class Org(db.Model):
    __tablename__ = 'orgs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)
    en_name = db.Column('en_name', db.String())
    head = db.Column('head', db.String())
    parent_id = db.Column('parent_id', db.Integer, db.ForeignKey('orgs.id'))
    children = db.relationship('Org', backref=db.backref('parent', remote_side=[id]))

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    @property
    def active_staff(self):
        return [s for s in self.staff if s.retired is not True]


class OrgStructure(db.Model):
    __tablename__ = 'org_structure'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    position = db.Column('position', db.String(), nullable=False)
    position_en = db.Column('position_en', db.String())


class Strategy(db.Model):
    __tablename__ = 'strategies'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False, info={'label': 'รหัสอ้างอิง'})
    created_at = db.Column('created_at', db.DateTime(),
                           server_default=func.now())
    content = db.Column('content', db.String(), nullable=False, info={'label': 'ยุทธศาสตร์'})
    org_id = db.Column('org_id', db.Integer(), db.ForeignKey('orgs.id'), nullable=False)
    org = db.relationship(Org, backref=db.backref('strategies', cascade='all, delete-orphan'))
    active = db.Column(db.Boolean(), default=True)

    def __str__(self):
        return f'{self.refno}. {self.content}'


class StrategyTactic(db.Model):
    __tablename__ = 'strategy_tactics'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False, info={'label': 'รหัสอ้างอิง'})
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    content = db.Column('content', db.String(), nullable=False, info={'label': 'แผนกลยุทธ์'})
    strategy_id = db.Column('strategy_id', db.Integer(),
                            db.ForeignKey('strategies.id'), nullable=False)
    strategy = db.relationship(Strategy, backref=db.backref('tactics', cascade='all, delete-orphan'))
    active = db.Column(db.Boolean(), default=True)

    def __str__(self):
        return f'{self.refno}. {self.content}'


class StrategyTheme(db.Model):
    __tablename__ = 'strategy_themes'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    content = db.Column('content', db.String(), nullable=False)
    tactic_id = db.Column('tactic_id', db.Integer(),
                          db.ForeignKey('strategy_tactics.id'), nullable=False)
    tactic = db.relationship(StrategyTactic, backref=db.backref('themes', cascade='all, delete-orphan'))
    active = db.Column(db.Boolean(), default=True)

    def __str__(self):
        return f'{self.refno}. {self.content}'


class StrategyActivity(db.Model):
    __tablename__ = 'strategy_activities'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    refno = db.Column('refno', db.String(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    content = db.Column('content', db.String, nullable=False)
    theme_id = db.Column('theme_id', db.Integer(), db.ForeignKey('strategy_themes.id'))
    theme = db.relationship(StrategyTheme, backref=db.backref('activities', cascade='all, delete-orphan'))
    active = db.Column(db.Boolean(), default=True)

    def __str__(self):
        return f'{self.refno}. {self.content}'


class RiskEvent(db.Model):
    __tablename__ = 'risk_events'
    id = db.Column('id', db.String(), primary_key=True)
    event = db.Column('event', db.String())


class KPI(db.Model):
    __tablename__ = 'kpis'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    created_by = db.Column('created_by', db.String())
    created_at = db.Column('created_at', db.DateTime(), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(), onupdate=func.now())
    updated_by = db.Column('updated_by', db.String())
    name = db.Column('name', db.String, nullable=False, info={'label': u'ชื่อตัวชี้วัด'})
    refno = db.Column('refno', db.String(), info={'label': u'รหัสอ้างอิงตัวชี้วัด'})
    intent = db.Column('intent', db.String(), info={'label': u'จุดประสงค์'})
    frequency = db.Column('frequency', db.Integer(), info={'label': u'ความถี่'})
    unit = db.Column('unit', db.String(), info={'label': u'หน่วย'})
    source = db.Column('source', db.String(), info={'label': u'แหล่งข้อมูล'})
    available = db.Column('available', db.Boolean(), info={'label': u'พร้อมใช้'})
    availability = db.Column('availability', db.String(), info={'label': u'การเข้าถึงข้อมูล',
                                                                'choices': [(c, c) for c in ['ไม่มีการรวบรวมข้อมูล',
                                                                                             'ผ่านระบบอัตโนมัติทั้งหมด',
                                                                                             'ต้องเตรียมข้อมูลเล็กน้อย',
                                                                                             'ต้องเตรียมข้อมูลอย่างมาก']]})
    type_ = db.Column('type_', db.String(), info={'label': 'ชนิดตัวชี้วัด', 'choices': [c for c in [('', ''), ('leading', 'ตัวชี้วัดนำ (leading)'), ('lagging', 'ตัวชี้วัดตาม (lagging)')]]})
    formula = db.Column('formula', db.String(), info={'label': u'สูตรคำนวณ'})
    keeper = db.Column('keeper', db.ForeignKey('staff_account.email'), info={'label': u'เก็บโดย'})
    note = db.Column('note', db.Text(), info={'label': u'หมายเหตุ'})
    target = db.Column('target', db.String(), info={'label': u'เป้าหมาย'})
    target_source = db.Column('target_source', db.String(), info={'label': u'ที่มาของการตั้งเป้าหมาย'})
    target_setter = db.Column('target_setter', db.ForeignKey('staff_account.email'), info={'label': u'ผู้ตั้งเป้าหมาย'})
    target_reporter = db.Column('target_reporter', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รายงานเป้าหมาย'})
    target_account = db.Column('target_account', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รับผิดชอบหลัก'})
    reporter = db.Column('reporter', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รายงาน'})
    consult = db.Column('consult', db.ForeignKey('staff_account.email'), info={'label': u'ที่ปรึกษา'})
    account = db.Column('account', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รับผิดชอบ'})
    informed = db.Column('informed', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รับรายงานหลัก'})
    pfm_account = db.Column('pfm_account', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รับดูแลประสิทธิภาพตัวชี้วัด'})
    pfm_responsible = db.Column('pfm_resposible', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รับผิดชอบประสิทธิภาพของตัวชี้วัด'})
    pfm_consult = db.Column('pfm_consult', db.ForeignKey('staff_account.email'), info={'label': u'ที่ปรึกษาประสิทธิภาพของตัวชี้วัด'})
    pfm_informed = db.Column('pfm_informed', db.ForeignKey('staff_account.email'), info={'label': u'ผู้รับรายงานเรื่องประสิทธิภาพตัวชี้วัดหลัก'})
    strategy_activity_id = db.Column('strategy_activity_id', db.ForeignKey('strategy_activities.id'))
    strategy_activity = db.relationship(StrategyActivity, backref=db.backref('kpis', cascade='all, delete-orphan'))
    strategy_id = db.Column('strategy_id', db.ForeignKey('strategies.id'))
    strategy = db.relationship(Strategy, backref=db.backref('kpis', cascade='all, delete-orphan'))
    reportlink = db.Column('reportlink', db.String(), info={'label': u'หน้าแสดงผล (dashboard)'})
    active = db.Column(db.Boolean(), default=True)
    risk_event = db.relationship(RiskEvent, backref=db.backref('kris'))
    risk_event_id = db.Column('risk_event_id', db.ForeignKey('risk_events.id'))


class KPICascade(db.Model):
    __tablename__ = 'kpi_cascades'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    kpi_id = db.Column('kpi_id', db.ForeignKey('kpis.id'))
    kpi = db.relationship(KPI, backref=db.backref('cascades', cascade='all, delete-orphan'))
    parent_id = db.Column('parent_id', db.ForeignKey('kpi_cascades.id'))
    children = db.relationship('KPICascade', backref=db.backref('parent', remote_side=[id]))
    goal = db.Column('goal', db.String(), nullable=False, info={'label': 'เป้าหมาย'})
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))


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


class Province(db.Model):
    __tablename__ = 'provinces'
    id = db.Column('id', db.Integer(), primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    name = db.Column('name', db.String(40), nullable=False)
    districts = db.relationship("District",
                                backref=db.backref('parent'))

    def __str__(self):
        return u'{}'.format(self.name)


class District(db.Model):
    __tablename__ = 'districts'
    id = db.Column('id', db.Integer(), primary_key=True)
    name = db.Column('name', db.String(40), nullable=False)
    code = db.Column('code', db.String(), nullable=False)
    province_id = db.Column(db.Integer(),
                            db.ForeignKey('provinces.id'))
    subdistricts = db.relationship('Subdistrict',
                                   backref=db.backref('district'))

    def __str__(self):
        return u'{}'.format(self.name)


class Subdistrict(db.Model):
    __tablename__ = 'subdistricts'
    id = db.Column('id', db.Integer(), primary_key=True)
    name = db.Column('name', db.String(80), nullable=False)
    code = db.Column('code', db.String(), nullable=False)
    district_id = db.Column(db.Integer(),
                            db.ForeignKey('districts.id'))
    zip_code_id = db.Column('zip_code_id', db.ForeignKey('zip_codes.id'))
    zip_code = db.relationship('Zipcode', backref=db.backref('subdistricts'))

    def __str__(self):
        return u'{}'.format(self.name)


class Zipcode(db.Model):
    __tablename__ = 'zip_codes'
    id = db.Column('id', db.Integer(), primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    zip_code = db.Column('zip_code', db.Integer(), nullable=False)

    def __str__(self):
        return u'{}'.format(self.zip_code)


class KPISchema(ma.SQLAlchemyAutoSchema):
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

    def __str__(self):
        return u'{}'.format(self.postal_code)

class Mission(db.Model):
    __tablename__ = 'missions'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)

    def __repr__(self):
        return u'{}:{}'.format(self.id, self.name)

    def __str__(self):
        return u'{}'.format(self.name)


cost_center_iocode_assoc = db.Table('cost_center_iocode_assoc',
                                    db.Column('cost_center_id', db.String(), db.ForeignKey('cost_centers.id'),
                                              primary_key=True),
                                    db.Column('iocode_id', db.String(), db.ForeignKey('iocodes.id'), primary_key=True),
                                    )


class CostCenter(db.Model):
    __tablename__ = 'cost_centers'
    id = db.Column('id', db.String(12), primary_key=True)

    def __repr__(self):
        return u'{}'.format(self.id)


class IOCode(db.Model):
    __tablename__ = 'iocodes'
    id = db.Column('id', db.String(16), primary_key=True)
    cost_center = db.relationship('CostCenter', backref=db.backref('iocodes'), secondary=cost_center_iocode_assoc)
    mission_id = db.Column('mission_id', db.Integer(), db.ForeignKey('missions.id'), nullable=False)
    mission = db.relationship('Mission', backref=db.backref('iocodes'))
    org_id = db.Column('org_id', db.Integer(), db.ForeignKey('orgs.id'), nullable=False)
    org = db.relationship('Org', backref=db.backref('iocodes'))
    name = db.Column('name', db.String(255), nullable=False)
    is_active = db.Column('is_active', db.Boolean(), default=True)

    def __repr__(self):
        return u'{}:{}:{}:{}'.format(self.id, self.name, self.org.name, self.mission)

    def __str__(self):
        return u'{}: {}'.format(self.id, self.name)

    def to_dict(self):
        return {
            'id': self.id,
            'costCenter': u'{}'.format(self.cost_center.id),
            'name': u'{}'.format(self.name),
            'org': u'{}'.format(self.org.name),
            'mission': u'{}'.format(self.mission.name)
        }


class ProductCode(db.Model):
    __tablename__ = 'product_codes'
    id = db.Column('id', db.String(12), primary_key=True)
    name = db.Column('name', db.String())
    branch = db.Column('branch', db.String())

    def __repr__(self):
        return '{} {} {}'.format(self.id, self.name, self.branch)


class OrgSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Org


class Holidays(db.Model):
    __tablename__ = 'holidays'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    holiday_date = db.Column('holiday_date', db.DateTime(timezone=True))
    holiday_name = db.Column('holiday_name', db.String())

    def tojson(self):
        return {"date": self.holiday_date, "name": self.holiday_name}


data_service_assoc = db.Table('data_service_assoc',
                              db.Column('data_id', db.Integer, db.ForeignKey('db_data.id'), primary_key=True),
                              db.Column('core_service_id', db.Integer, db.ForeignKey('db_core_services.id'),
                                        primary_key=True)
                              )

data_process_assoc = db.Table('data_process_assoc',
                              db.Column('data_id', db.Integer, db.ForeignKey('db_data.id'), primary_key=True),
                              db.Column('process_id', db.Integer, db.ForeignKey('db_processes.id'), primary_key=True),
                              )

data_process_staff_assoc = db.Table('data_process_staff_assoc',
                                    db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id'),
                                              primary_key=True),
                                    db.Column('process_id', db.Integer, db.ForeignKey('db_processes.id'),
                                              primary_key=True),
                                    )

service_staff_assoc = db.Table('service_staff_assoc',
                               db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id'),
                                         primary_key=True),
                               db.Column('core_service_id', db.Integer, db.ForeignKey('db_core_services.id'),
                                         primary_key=True),
                               )

dataset_service_assoc = db.Table('dataset_service_assoc',
                                 db.Column('dataset_id', db.Integer, db.ForeignKey('db_datasets.id'), primary_key=True),
                                 db.Column('core_service_id', db.Integer, db.ForeignKey('db_core_services.id'),
                                           primary_key=True)
                                 )

dataset_process_assoc = db.Table('dataset_process_assoc',
                                 db.Column('dataset_id', db.Integer, db.ForeignKey('db_datasets.id'), primary_key=True),
                                 db.Column('process_id', db.Integer, db.ForeignKey('db_processes.id'),
                                           primary_key=True),
                                 )

dataset_kpi_assoc = db.Table('dataset_kpi_assoc',
                             db.Column('dataset_id', db.Integer, db.ForeignKey('db_datasets.id'), primary_key=True),
                             db.Column('kpi_id', db.Integer, db.ForeignKey('kpis.id'), primary_key=True),
                             )

kpi_service_assoc = db.Table('kpi_service_assoc',
                             db.Column('kpi_id', db.Integer, db.ForeignKey('kpis.id'), primary_key=True),
                             db.Column('core_service_id', db.Integer, db.ForeignKey('db_core_services.id'),
                                       primary_key=True)
                             )

kpi_process_assoc = db.Table('kpi_process_assoc',
                             db.Column('kpi_id', db.Integer, db.ForeignKey('kpis.id'), primary_key=True),
                             db.Column('process_id', db.Integer, db.ForeignKey('db_processes.id'), primary_key=True)
                             )

pdpa_coordinators = db.Table('pdpa_coordinators',
                             db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id'), primary_key=True),
                             db.Column('db_core_service_id', db.Integer, db.ForeignKey('db_core_services.id'),
                                       primary_key=True)
                             )

from app.staff.models import StaffAccount


class CoreService(db.Model):
    __tablename__ = 'db_core_services'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    service = db.Column('service', db.String(255), nullable=False, info={'label': u'บริการ'})
    mission_id = db.Column('mission_id', db.ForeignKey('missions.id'))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    mission = db.relationship(Mission, backref=db.backref('services', lazy='dynamic',
                                                          cascade='all, delete-orphan'))
    data = db.relationship('Data', secondary=data_service_assoc, lazy='subquery',
                           backref=db.backref('core_services', lazy=True))
    kpis = db.relationship(KPI, secondary=kpi_service_assoc, lazy='subquery',
                           backref=db.backref('core_services', lazy=True))
    datasets = db.relationship('Dataset', secondary=dataset_service_assoc, lazy='subquery',
                               backref=db.backref('core_services', lazy=True))
    pdpa_coordinators = db.relationship(StaffAccount, secondary=pdpa_coordinators, lazy='subquery',
                                        backref=db.backref('pdpa_services', lazy=True))
    staff = db.relationship('StaffAccount', secondary=service_staff_assoc, lazy='subquery',
                            backref=db.backref('core_services', lazy=True))

    def __str__(self):
        return u'{}'.format(self.service)


class Data(db.Model):
    __tablename__ = 'db_data'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255), nullable=False, info={'label': u'ข้อมูล'})
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))


class Process(db.Model):
    __tablename__ = 'db_processes'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    category = db.Column('category', db.String(), nullable=False,
                         info={'label': u'กลุ่มงาน', 'choices': [c for c in
                                                                 [('back_office', 'Back Office'),
                                                                  ('regulation', 'Law/Compliance'),
                                                                  ('performance', 'Performance Management'),
                                                                  ('crm', 'Experience Management')]]
                               })
    name = db.Column('name', db.String(255), nullable=False, info={'label': u'กระบวนการ'})
    org_id = db.Column('org_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('processes', lazy=True))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    data = db.relationship(Data, secondary=data_process_assoc, lazy='subquery',
                           backref=db.backref('processes', lazy=True))
    kpis = db.relationship(KPI, secondary=kpi_process_assoc, lazy='subquery',
                           backref=db.backref('processes', lazy=True))
    datasets = db.relationship('Dataset', secondary=dataset_process_assoc, lazy='subquery',
                               backref=db.backref('processes', lazy=True))
    staff = db.relationship('StaffAccount', secondary=data_process_staff_assoc, lazy='subquery',
                            backref=db.backref('processes', lazy=True))
    parent_id = db.Column('parent_id', db.ForeignKey('db_processes.id'))
    subprocesses = db.relationship('Process', backref=db.backref('parent', remote_side=[id]))
    is_expired = db.Column('is_expired', db.Boolean(), default=False)
    expired_at = db.Column('expired_at', db.DateTime(timezone=True))
    expired_by_account_id = db.Column('expired_by_account_id', db.ForeignKey('staff_account.id'))
    def __str__(self):
        return self.name


class Dataset(db.Model):
    __tablename__ = 'db_datasets'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    reference = db.Column('reference', db.String(255),
                          nullable=False, info={'label': u'รหัสข้อมูล'})
    name = db.Column('name', db.String(255), info={'label': u'ชื่อ'})
    desc = db.Column('desc', db.Text(), info={'label': u'รายละเอียด'})
    # goal = db.Column('goal', db.Text(), info={'label': u'วัตถุประสงค์'})
    # data_type = db.Column('data_type', db.String(),
    #                      info={'label': u'ประเภทชุดข้อมูล', 'choices': [(c, c) for c in ['ข้อมูลระเบียน', 'ข้อมูลสถิติ',
    #                                                                             'ข้อมูลหลากหลายประเภท']]})
    # data_type = db.Column('data_type', db.String(),
    #                       info={'label': u'ประเภทชุดข้อมูล',
    #                             'choices': [(c, c) for c in ['ข้อมูลระเบียน', 'ข้อมูลสถิติ',
    #                                                          'ข้อมูลหลากหลายประเภท']]})
    # frequency = db.Column('frequency', db.String(),
    #                       info={'label': u'หน่วยความถี่ของการปรับปรุงข้อมูล',
    #                             'choices': [(c, c) for c in ['ปี', 'ครึ่งปี', 'ไตรมาส', 'เดือน', 'สัปดาห์', 'วัน', 'ตามเวลาจริง',
    #                                                          'ไม่มีการปรับปรุงหลังจากการจัดเก็บข้อมูล']]})
    source_url = db.Column('source_url', db.Text(), info={'label': u'URL แหล่งข้อมูล'})
    data_id = db.Column('data_id', db.ForeignKey('db_data.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    maintainer_id = db.Column('maintainer_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship('StaffAccount', foreign_keys=[creator_id],
                            backref=db.backref('datasets_creator', lazy='dynamic'))
    maintainer = db.relationship('StaffAccount', foreign_keys=[maintainer_id],
                              backref=db.backref('datasets_maintainer', lazy='dynamic'))
    sensitive = db.Column('sensitive', db.Boolean(), default=False, info={'label': u'ข้อมูลอ่อนไหว'})
    personal = db.Column('personal', db.Boolean(), default=False, info={'label': u'ข้อมูลส่วนบุคคล'})
    data = db.relationship(Data, backref=db.backref('datasets', lazy='dynamic', cascade='all, delete-orphan'))
    kpis = db.relationship(KPI, secondary=dataset_kpi_assoc, lazy='subquery',
                           backref=db.backref('datasets', lazy=True))
    tags = db.relationship('DataTag', secondary=dataset_tag_assoc, lazy='subquery',
                           backref=db.backref('datasets', lazy=True))


class DataTag(db.Model):
    __tablename__ = 'db_datatags'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    tag = db.Column('tag', db.String(), nullable=False, unique=True)

    def __str__(self):
        return u'{}'.format(self.tag)

    def to_dict(self):
        return {
            'id': self.tag,
            'text': self.tag
        }


class DataFile(db.Model):
    __tablename__ = 'db_files'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    data_set_id = db.Column('data_set_id', db.ForeignKey('db_datasets.id'))
    name = db.Column('name', db.String(255), info={'label': u'ชื่อ'})
    dataset = db.relationship('Dataset', backref=db.backref('files', lazy='dynamic', cascade='all, delete-orphan'))
    desc = db.Column('desc', db.Text(), info={'label': u'รายละเอียด'})
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    url = db.Column('url', db.String())
    # file_type = db.Column('file_type', db.String(),
    #                      info={'label': u'รูปแบบของไฟล์ชุดข้อมูล', 'choices': [(c, c) for c in ['excel/csv', 'text/word',
    #                                                                             'pdf', 'database', 'image', 'video']]})


ropa_subject_assoc = db.Table('ropa_service_assoc',
                              db.Column('ropa_id', db.Integer, db.ForeignKey('db_ropas.id'), primary_key=True),
                              db.Column('subject_id', db.Integer, db.ForeignKey('db_data_subjects.id'),
                                        primary_key=True))


class DataSubject(db.Model):
    __tablename__ = 'db_data_subjects'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    subject = db.Column('subject', db.String(), nullable=False, info={'label': u'เจ้าของข้อมูล'})


class DataStorage(db.Model):
    __tablename__ = 'db_storages'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    type_ = db.Column('type', db.String(), nullable=False, info={'label': u'ประเภท',
                                                                 'choices': [(c, c) for c in
                                                                             [u'ฐานข้อมูล',
                                                                              u'Excel',
                                                                              'Google sheet',
                                                                              u'กระดาษ',
                                                                              u'อื่น ๆ']]})
    desc = db.Column('desc', db.String(), info={'label': u'รายละเอียด'})


class ROPA(db.Model):
    __tablename__ = 'db_ropas'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    dataset_id = db.Column('dataset_id', db.ForeignKey('db_datasets.id'))
    dataset = db.relationship(Dataset, backref=db.backref('ropa', uselist=False))
    major_objective = db.Column('major_objective', db.Text(), info={'label': u'จุดประสงค์หลักในการเก็บข้อมูล'})
    minor_objective = db.Column('minor_objective', db.Text(), info={'label': u'จุดประสงค์รองในการเก็บข้อมูล'})
    subjects = db.relationship(DataSubject,
                               secondary=ropa_subject_assoc,
                               lazy='subquery',
                               backref=db.backref('subjects', lazy=True))
    personal_data = db.Column('personal_data', db.String(), info={'label': u'ประเภทข้อมูลส่วนบุคคล'})
    personal_data_desc = db.Column('personal_data_desc', db.Text(), info={'label': u'รายละเอียดข้อมูลส่วนบุคคล'})
    sensitive_data = db.Column('sensitive_data', db.Text(), info={'label': u'ข้อมูลอ่อนไหว'})
    consent_required = db.Column('consent_required', db.Boolean(), default=False, info={'label': u'ต้องการ consent'})
    amount = db.Column('amount', db.String(), info={'label': u'ปริมาณข้อมูล'})
    is_primary_data = db.Column('is_primary_data', db.Boolean(), info={'label': u'เก็บข้อมูลจากเจ้าของโดยตรงหรือไม่'})
    law_basis = db.Column('law_basis', db.Text(), info={'label': u'แหล่งที่มาของข้อมูล',
                                                        'choices': [(c, c) for c in
                                                                    [u'ฐานจัดทำหมายเหตุ/วิจัย/สถิติ',
                                                                     u'ฐานป้องกันหรือระงับอันตรายต่อชีวิต',
                                                                     u'ฐานปฏิบัติตามสัญญา',
                                                                     u'ฐานประโยชน์สาธารณะ',
                                                                     u'ฐานประโยชน์โดยชอบด้วยกฎหมาย',
                                                                     u'ฐานการปฏิบัติตามกฎหมาย',
                                                                     u'ฐานความยินยอม']]})
    source = db.Column('source', db.Text(), info={'label': u'แหล่งที่มาของข้อมูล'})
    format = db.Column('format', db.Text(), info={'label': u'รูปแบบการเก็บข้อมูล'})
    storage = db.Column('storage', db.Text(), info={'label': u'สถานที่เก็บข้อมูล'})
    duration = db.Column('duration', db.Text(), info={'label': u'ระยะเวลาในการเก็บข้อมูล'})
    destroy_method = db.Column('destroy_method', db.Text(), info={'label': u'การทำลายข้อมูลหลังหมดอายุ'})
    inside_sharing = db.Column('inside_sharing', db.Text(), info={'label': u'การแลกเปลี่ยนข้อมูลในหน่วยงาน'})
    outside_sharing = db.Column('outside_sharing', db.Text(), info={'label': u'การแลกเปลี่ยนข้อมูลนอกหน่วยงาน'})
    intl_sharing = db.Column('intl_sharing', db.Text(), info={'label': u'มาตรการในการแลกเปลี่ยนข้อมูลต่างประเทศ'})
    security_measure = db.Column('security_measure', db.Text(),
                                 info={'label': u'มาตรการควบคุมข้อมูลส่วนบุคคลในปัจจุบัน'})
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    updater_id = db.Column('updater_id', db.ForeignKey('staff_account.id'))
    updater = db.relationship(StaffAccount)


class Dashboard(db.Model):
    __tablename__ = 'dashboard'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(), nullable=False)
    description = db.Column('description', db.String(), nullable=False)
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    url = db.Column('url', db.String())
    mission_id = db.Column('mission_id', db.Integer(), db.ForeignKey('missions.id'), nullable=False)
    mission = db.relationship('Mission', backref=db.backref('dashboard'))
