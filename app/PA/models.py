from sqlalchemy import desc

from app.main import db
from app.models import Org, KPI
from app.staff.models import StaffAccount, StaffJobPosition

item_kpi_item_assoc_table = db.Table('item_kpi_item_assoc_assoc',
                                     db.Column('item_id', db.ForeignKey('pa_items.id')),
                                     db.Column('kpi_item_id',
                                               db.ForeignKey('pa_kpi_items.id')),
                                     )

pa_committee_assoc_table = db.Table('pa_committee_assoc',
                                    db.Column('pa_agreement_id', db.ForeignKey('pa_agreements.id')),
                                    db.Column('committee_id',
                                              db.ForeignKey('pa_committees.id')),
                                    )

pa_round_employment_assoc_table = db.Table('pa_round_employment_assoc',
                                           db.Column('pa_round_id', db.ForeignKey('pa_rounds.id')),
                                           db.Column('employment_id',
                                                     db.ForeignKey('staff_employments.id')),
                                           )


class PARound(db.Model):
    __tablename__ = 'pa_rounds'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column('start', db.Date())
    end = db.Column('end', db.Date())
    employments = db.relationship('StaffEmployment', secondary=pa_round_employment_assoc_table)
    desc = db.Column('desc', db.String())
    is_closed = db.Column('is_closed', db.Boolean(), default=False)

    def __str__(self):
        return "{} - {}".format(self.start.strftime('%d/%m/%Y'), self.end.strftime('%d/%m/%Y'))


class PAAgreement(db.Model):
    __tablename__ = 'pa_agreements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('pa_agreements', lazy='dynamic', cascade='all, delete-orphan'))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    round_id = db.Column('round_id', db.ForeignKey('pa_rounds.id'))
    round = db.relationship(PARound, backref=db.backref('agreements', lazy='dynamic'))
    committees = db.relationship('PACommittee', secondary=pa_committee_assoc_table)
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    submitted_at = db.Column('submitted_at', db.DateTime(timezone=True))
    evaluated_at = db.Column('evaluated_at', db.DateTime(timezone=True))
    performance_score = db.Column('performance_score', db.Numeric())
    competency_score = db.Column('competency_score', db.Numeric())
    inform_score_at = db.Column('inform_score_at', db.DateTime(timezone=True))
    accept_score_at = db.Column('accept_score_at', db.DateTime(timezone=True))

    @property
    def total_percentage(self):
        return sum([item.percentage for item in self.pa_items])

    @property
    def submitted(self):
        req = self.requests.order_by(desc(PARequest.id)).first()
        if req and req.for_ == 'ขอรับการประเมิน':
            return True
        else:
            return False

    @property
    def editable(self):
        req = self.requests.order_by(desc(PARequest.id)).first()
        if req and req.for_ == 'ขอแก้ไข':
            return True if req.status == 'อนุมัติ' else False
        elif req and req.for_ == 'ขอรับรอง':
            return True if req.status == 'ไม่อนุมัติ' else False
        elif self.approved_at:
            return False
        elif self.submitted:
            return False
        return True

    def can_enter_result(self):
        return True if self.approved_at else False


class PARequest(db.Model):
    __tablename__ = 'pa_requests'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pa_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    pa = db.relationship('PAAgreement',
                         foreign_keys=[pa_id],
                         backref=db.backref('requests',
                                            lazy='dynamic',
                                            cascade='all, delete-orphan'),
                         order_by='PARequest.created_at.desc()')
    supervisor_id = db.Column('supervisor_id', db.ForeignKey('staff_account.id'))
    supervisor = db.relationship('StaffAccount', backref=db.backref('request_supervisor', lazy='dynamic'),
                                 foreign_keys=[supervisor_id])
    for_ = db.Column(db.String(), nullable=False, info={'label': 'สำหรับ',
                                                        'choices': [(c, c) for c in
                                                                    ('ขอรับรอง', 'ขอแก้ไข', 'ขอรับการประเมิน')]})
    status = db.Column(db.String(), info={'label': 'สถานะ',
                                          'choices': [(c, c) for c in ('อนุมัติ', 'ไม่อนุมัติ')]})
    supervisor_comment = db.Column('supervisor_comment', db.Text(), info={'label': 'Comment'})
    responded_at = db.Column('responded_at', db.DateTime(timezone=True))
    submitted_at = db.Column('submitted_at', db.DateTime(timezone=True))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    detail = db.Column('detail', db.Text(), info={'label': 'รายละเอียด'})


class PALevel(db.Model):
    __tablename__ = 'pa_levels'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    level = db.Column('level', db.String())
    order = db.Column('order', db.Integer())

    def __str__(self):
        return self.level


class PAKPI(db.Model):
    __tablename__ = 'pa_kpis'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pa_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    pa = db.relationship('PAAgreement',
                         backref=db.backref('kpis', cascade='all, delete-orphan'))
    detail = db.Column(db.Text())
    source = db.Column(db.Text())
    type = db.Column(db.String(), info={'label': 'ประเภท',
                                        'choices': [(c, c) for c in
                                                    ('ปริมาณ', 'คุณภาพ', 'เวลา', 'ความคุ้มค่า', 'ความพึงพอใจ')]})

    def __str__(self):
        return f'{self.detail} (ประเภท {self.type})'


class PAKPIItem(db.Model):
    __tablename__ = 'pa_kpi_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    level_id = db.Column('level_id', db.ForeignKey('pa_levels.id'))
    level = db.relationship(PALevel, uselist=False)
    kpi_id = db.Column(db.ForeignKey('pa_kpis.id'))
    kpi = db.relationship('PAKPI', backref=db.backref('pa_kpi_items',
                                                      order_by='PAKPIItem.level_id',
                                                      cascade='all, delete-orphan'))
    goal = db.Column('goal', db.Text())

    def __str__(self):
        return f'{self.kpi.detail} [เป้าหมาย: {self.goal} ({self.level} คะแนน)]'


class PAKPIJobPosition(db.Model):
    __tablename__ = 'pa_kpi_job_positions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    detail = db.Column(db.Text())
    job_position_id = db.Column(db.ForeignKey('staff_job_positions.id'))
    job_position = db.relationship('StaffJobPosition',
                                   backref=db.backref('kpi_job_position'))
    type = db.Column(db.String(), info={'label': 'ประเภท',
                                        'choices': [(c, c) for c in
                                                    ('ปริมาณ', 'คุณภาพ', 'เวลา', 'ความคุ้มค่า', 'ความพึงพอใจ')]})


class PAKPIItemJobPosition(db.Model):
    __tablename__ = 'pa_kpi_item_job_positions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    level_id = db.Column('level_id', db.ForeignKey('pa_levels.id'))
    level = db.relationship(PALevel, uselist=False)
    job_kpi_id = db.Column(db.ForeignKey('pa_kpi_job_positions.id'))
    job_kpi = db.relationship('PAKPIJobPosition', backref=db.backref('pa_kpi_job_positions',
                                                      order_by='PAKPIItemJobPosition.level_id',
                                                      cascade='all, delete-orphan'))
    goal = db.Column('goal', db.Text())

    def __str__(self):
        return f'{self.job_kpi.detail} [เป้าหมาย: {self.goal} ({self.level} คะแนน)]'


class PAItemCategory(db.Model):
    __tablename__ = 'pa_item_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column('category', db.String(), nullable=False)

    def __str__(self):
        return self.category


class PAItem(db.Model):
    __tablename__ = 'pa_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_id = db.Column(db.ForeignKey('pa_item_categories.id'))
    category = db.relationship(PAItemCategory, backref=db.backref('pa_items', lazy='dynamic'))
    task = db.Column(db.Text(), info={'label': 'รายละเอียด'})
    report = db.Column(db.Text(), info={'label': 'ผลการดำเนินการ'})
    percentage = db.Column(db.Numeric())
    pa_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    pa = db.relationship('PAAgreement', backref=db.backref('pa_items', cascade='all, delete-orphan'))
    kpi_items = db.relationship('PAKPIItem', secondary=item_kpi_item_assoc_table)
    number = db.Column(db.Integer)
    org_kpi_id = db.Column('org_kpi_id', db.ForeignKey('kpis.id'))
    org_kpi = db.relationship(KPI, backref=db.backref('kpi_pa_items', lazy='dynamic'))

    def __str__(self):
        return self.task

    def average_score(self, scoresheet):
        score = 0
        n = 0
        for s in self.pa_score_item:
            if s.score_sheet_id == scoresheet.id:
                if s.score:
                    score += s.score
                    n += 1
        return score / n

    def total_score(self, scoresheet):
        score = 0
        n = 0
        for s in self.pa_score_item:
            if s.score_sheet_id == scoresheet.id:
                if s.score:
                    score += s.score
                    n += 1
        return (score / n) * self.percentage


class PACommittee(db.Model):
    __tablename__ = 'pa_committees'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    org_id = db.Column(db.ForeignKey('orgs.id'))
    staff = db.relationship('StaffAccount', backref=db.backref('commitee', lazy='dynamic'),
                            foreign_keys=[staff_account_id])
    org = db.relationship(Org, backref=db.backref('org_committee', lazy='dynamic'))
    round_id = db.Column(db.ForeignKey('pa_rounds.id'))
    round = db.relationship(PARound, backref=db.backref('round_committee', lazy='dynamic'))
    role = db.Column('role', db.String(), info={'label': 'ประเภท',
                                                'choices': [(c, c) for c in ('ประธานกรรมการ', 'กรรมการ')]})
    subordinate_account_id = db.Column(db.ForeignKey('staff_account.id'))
    subordinate = db.relationship('StaffAccount', backref=db.backref('subordinate_committee', lazy='dynamic'),
                                  foreign_keys=[subordinate_account_id])

    def __str__(self):
        return self.staff.fullname


class PAScoreSheet(db.Model):
    __tablename__ = 'pa_score_sheets'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pa_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    pa = db.relationship('PAAgreement', backref=db.backref('pa_score_sheet',
                                                           lazy='dynamic',
                                                           cascade='all, delete-orphan'))
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('pa_scoresheets',
                                                             cascade='all, delete-orphan'))
    committee_id = db.Column('committee_id', db.ForeignKey('pa_committees.id'))
    committee = db.relationship('PACommittee',
                                backref=db.backref('committee_score_sheet', cascade='all, delete-orphan'))
    is_consolidated = db.Column('is_consolidated', db.Boolean(), default=False)
    is_final = db.Column('is_final', db.Boolean(), default=False)
    is_appproved = db.Column('is_appproved', db.Boolean(), default=False)
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    confirm_at = db.Column('confirm_at', db.DateTime(timezone=True))
    strengths = db.Column('strengths', db.Text())
    weaknesses = db.Column('weaknesses', db.Text())

    def get_score_sheet_item(self, pa_item_id, kpi_item_id):
        return self.score_sheet_items.filter_by(item_id=pa_item_id,
                                                kpi_item_id=kpi_item_id).first()

    def get_core_competency_score_item(self, comp_item_id):
        return self.competency_score_items.filter_by(item_id=comp_item_id).first()

    def competency_total(self):
        score = 0
        for c in self.competency_score_items:
            if c.score_sheet_id == self.id:
                if c.score:
                    score += c.score * 10
        return score

    def competency_net_score(self):
        score = 0
        for c in self.competency_score_items:
            if c.score_sheet_id == self.id:
                if c.score:
                    score += c.score * 10
        net_score = (score / 700) * 20
        return round(net_score,2)


class PAScoreSheetItem(db.Model):
    __tablename__ = 'pa_score_sheet_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score_sheet_id = db.Column(db.ForeignKey('pa_score_sheets.id'))
    score_sheet = db.relationship('PAScoreSheet',
                                  backref=db.backref('score_sheet_items',
                                                     lazy='dynamic',
                                                     cascade='all, delete-orphan'))
    item_id = db.Column(db.ForeignKey('pa_items.id'))
    item = db.relationship('PAItem', backref=db.backref('pa_score_item',
                                                        cascade='all, delete-orphan'))
    kpi_item_id = db.Column(db.ForeignKey('pa_kpi_items.id'))
    kpi_item = db.relationship('PAKPIItem', backref=db.backref('sore_sheet_kpi_item',
                                                               cascade='all, delete-orphan'))
    score = db.Column('score', db.Numeric())
    comment = db.Column('comment', db.Text())

    @property
    def score_tag(self):
        return f'<div class="control"><div class="tags has-addons"><span class="tag">{self.score_sheet.committee.staff.fullname}</span><span class="tag is-info">{self.score}</span></div></div>'


class PACoreCompetencyItem(db.Model):
    __tablename__ = 'pa_core_competency_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scoresheet_id = db.Column(db.ForeignKey('pa_score_sheets.id'))
    topic = db.Column('topic', db.String(), nullable=False, info={'label': 'หัวข้อ'})
    desc = db.Column('desc', db.Text(), info={'label': 'คำอธิบาย'})
    score = db.Column('score', db.Numeric(), info={'label': 'คะแนนเต็ม'})

    def competency_multiply(self, scoresheet):
        for c in self.core_score_core_item:
            if c.score_sheet_id == scoresheet.id:
                if c.score:
                    score = c.score
        return score * self.score


class PACoreCompetencyScoreItem(db.Model):
    __tablename__ = 'pa_core_competency_score_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score_sheet_id = db.Column(db.ForeignKey('pa_score_sheets.id'))
    score_sheet = db.relationship('PAScoreSheet',
                                  backref=db.backref('competency_score_items',
                                                     lazy='dynamic',
                                                     cascade='all, delete-orphan'))
    item_id = db.Column(db.ForeignKey('pa_core_competency_items.id'))
    item = db.relationship('PACoreCompetencyItem', backref=db.backref('core_score_core_item'))
    score = db.Column('score', db.Numeric())
    comment = db.Column('comment', db.Text())


class PAApprovedScoreSheet(db.Model):
    __tablename__ = 'pa_approved_score_sheets'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score_sheet_id = db.Column(db.ForeignKey('pa_score_sheets.id'))
    score_sheet = db.relationship('PAScoreSheet',
                                  backref=db.backref('approved_score_sheet',
                                                     cascade='all, delete-orphan'))
    committee_id = db.Column('committee_id', db.ForeignKey('pa_committees.id'))
    committee = db.relationship('PACommittee', backref=db.backref('committee_approved_score_sheet'),
                                foreign_keys=[committee_id])
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))


class PAFunctionalCompetency(db.Model):
    __tablename__ = 'pa_functional_competency'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column('code', db.String(), nullable=False, info={'label': 'รหัส'})
    name = db.Column('name', db.String(), info={'label': 'คำอธิบาย'})
    desc = db.Column('desc', db.String(), info={'label': 'ความหมาย'})
    job_position_id = db.Column(db.ForeignKey('staff_job_positions.id'))
    job_position = db.relationship('StaffJobPosition',
                                   backref=db.backref('fc_job_position'))

    def __str__(self):
        return f'{self.code} {self.name}'


class PAFunctionalCompetencyLevel(db.Model):
    __tablename__ = 'pa_functional_competency_levels'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order = db.Column('order', db.Integer())
    period = db.Column('period', db.String())
    desc = db.Column('desc', db.String())

    def __str__(self):
        return f'ระดับ {self.order} ({self.desc})'


class PAFunctionalCompetencyIndicator(db.Model):
    __tablename__ = 'pa_functional_competency_indicators'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    function_id = db.Column(db.ForeignKey('pa_functional_competency.id'))
    functional = db.relationship('PAFunctionalCompetency',
                                   backref=db.backref('indicator_functional', lazy='dynamic'))
    level_id = db.Column(db.ForeignKey('pa_functional_competency_levels.id'))
    level = db.relationship('PAFunctionalCompetencyLevel',
                                 backref=db.backref('indicator_level', lazy='dynamic'))
    indicator = db.Column('indicator', db.String(), nullable=False, info={'label': 'ตัวชี้วัดพฤติกรรม'})

    def __str__(self):
        return f'ตัวชี้วัด {self.functional.code} {self.indicator}'


class PAFunctionalCompetencyCriteria(db.Model):
    __tablename__ = 'pa_functional_competency_criteria'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    criterion = db.Column('criterion', db.String(), info={'label': 'ระดับ'})

    def __str__(self):
        return f'{self.criterion}'


class PAFunctionalCompetencyRound(db.Model):
    __tablename__ = 'pa_functional_competency_round'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column('start', db.Date())
    end = db.Column('end', db.Date())
    desc = db.Column(db.String(), info={'label': 'รอบ'})
    is_closed = db.Column(db.Boolean(), default=False)

    def __str__(self):
        return f'{self.desc}'


class PAFunctionalCompetencyEvaluation(db.Model):
    __tablename__ = 'pa_functional_competency_evaluations'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('fc_staff', lazy='dynamic'), foreign_keys=[staff_account_id])
    evaluator_account_id = db.Column(db.ForeignKey('staff_account.id'))
    evaluator = db.relationship(StaffAccount, backref=db.backref('fc_evaluator', lazy='dynamic'), foreign_keys=[evaluator_account_id])
    round_id = db.Column(db.ForeignKey('pa_functional_competency_round.id'))
    round = db.relationship(PAFunctionalCompetencyRound, backref=db.backref('fc_round'))
    pa_id = db.Column(db.ForeignKey('pa_agreements.id'))
    updated_at = db.Column(db.DateTime(timezone=True))
    confirm_at = db.Column(db.DateTime(timezone=True))

    def __str__(self):
        return "{}->{}".format(self.evaluator.email, self.staff.email)


class PAFunctionalCompetencyEvaluationIndicator(db.Model):
    __tablename__ = 'pa_functional_competency_evaluation_indicators'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    evaluation_id = db.Column(db.ForeignKey('pa_functional_competency_evaluations.id'))
    evaluation = db.relationship(PAFunctionalCompetencyEvaluation, backref=db.backref('evaluation_eva_indicator'))
    indicator_id = db.Column(db.ForeignKey('pa_functional_competency_indicators.id'))
    indicator = db.relationship(PAFunctionalCompetencyIndicator, backref=db.backref('indicator_eva_indicator'))
    criterion_id = db.Column(db.ForeignKey('pa_functional_competency_criteria.id'))
    criterion = db.relationship(PAFunctionalCompetencyCriteria, backref=db.backref('criterion_eva_indicator'))


class IDP(db.Model):
    __tablename__ = 'idps'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('idp_staff', lazy='dynamic', cascade='all, delete-orphan'),
                            foreign_keys=[staff_account_id])
    approver_account_id = db.Column(db.ForeignKey('staff_account.id'))
    approver = db.relationship(StaffAccount, backref=db.backref('idp_approver', lazy='dynamic', cascade='all, delete-orphan')
                               ,foreign_keys=[approver_account_id])
    round_id = db.Column(db.ForeignKey('pa_functional_competency_round.id'))
    round = db.relationship(PAFunctionalCompetencyRound, backref=db.backref('idp_round'))
    submitted_at = db.Column('submitted_at', db.DateTime(timezone=True))
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    evaluated_at = db.Column('evaluated_at', db.DateTime(timezone=True))
    accepted_at = db.Column('accepted_at', db.DateTime(timezone=True))
    approver_review = db.Column(db.String())
    achievement_percentage = db.Column(db.Float())


class IDPItem(db.Model):
    __tablename__ = 'idp_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    idp_id = db.Column(db.ForeignKey('idps.id'))
    idp = db.relationship('IDP', backref=db.backref('idp_item', lazy='dynamic', cascade='all, delete-orphan'))
    plan = db.Column(db.String())
    goal = db.Column(db.String())
    start = db.Column(db.Date())
    end = db.Column(db.Date())
    budget = db.Column(db.Integer())
    is_success = db.Column(db.Boolean(), default=False)
    result_detail = db.Column(db.String())
    learning_type_id = db.Column(db.ForeignKey('idp_learning_type.id'))
    learning_type = db.relationship('IDPLearningType', backref=db.backref('learning_type_items'))
    approver_comment = db.Column(db.String())


class IDPLearningType(db.Model):
    __tablename__ = 'idp_learning_type'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(db.String())

