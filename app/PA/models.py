from sqlalchemy import desc

from app.main import db
from app.models import Org
from app.staff.models import StaffAccount, StaffEmployment

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
    # is_closed = db.Column('is_closed', db.Boolean(), default=False)

    def __str__(self):
        return "{} - {}".format(self.start.strftime('%d/%m/%Y'), self.end.strftime('%d/%m/%Y'))


class PAAgreement(db.Model):
    __tablename__ = 'pa_agreements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('pa_agreements', cascade='all, delete-orphan'))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    round_id = db.Column('round_id', db.ForeignKey('pa_rounds.id'))
    round = db.relationship(PARound, backref=db.backref('agreements', lazy='dynamic'))
    committees = db.relationship('PACommittee', secondary=pa_committee_assoc_table)
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
    performance_score = db.Column('performance_score', db.Numeric())
    competency_score = db.Column('competency_score', db.Numeric())

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
        return (score / 700) * 20


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

#
# class PAFunctionalCompetency(db.Model):
#     __tablename__ = 'pa_functional_competency'
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     code = db.Column('code', db.String(), nullable=False, info={'label': 'รหัส'})
#     score = db.Column('score', db.Numeric(), info={'label': 'คะแนนเต็ม'})
#
#
# class PAFunctionalCompetencyItem(db.Model):
#     __tablename__ = 'pa_functional_competency_items'
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     function_id = db.Column(db.ForeignKey('pa_functional_competency.id'))
#     topic = db.Column('topic', db.String(), nullable=False, info={'label': 'หัวข้อ'})
#     desc = db.Column('desc', db.Text(), info={'label': 'คำอธิบาย'})
#
#
# class PAFunctionalCompetency(db.Model):
#     __tablename__ = 'pa_functional_competency_items'
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     code = db.Column('code', db.String(), nullable=False, info={'label': 'รหัส'})
#     desc = db.Column('desc', db.Text(), info={'label': 'คำอธิบาย'})
#     desc = db.Column('desc', db.Text(), info={'label': 'คำอธิบาย'})