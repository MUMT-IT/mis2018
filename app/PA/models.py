from wtforms import widgets

from app.main import db
from app.models import Org
from app.staff.models import StaffAccount

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


class PARound(db.Model):
    __tablename__ = 'pa_rounds'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column('start', db.Date())
    end = db.Column('end', db.Date())

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


class PARequest(db.Model):
    __tablename__ = 'pa_requests'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pa_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    pa = db.relationship('PAAgreement', foreign_keys=[pa_id],
                         backref=db.backref('requests', lazy='dynamic'),
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
    pa = db.relationship('PAAgreement', backref=db.backref('kpis'), foreign_keys=[pa_id])
    detail = db.Column(db.Text())
    type = db.Column(db.String(), info={'label': 'ประเภท',
                                        'choices': [(c, c) for c in
                                                    ('ปริมาณ', 'คุณภาพ', 'เวลา', 'ความคุ้มค่า', 'ความพึงพอใจ')]})

    def __str__(self):
        return f'ประเภท{self.type} {self.detail}'


class PAKPIItem(db.Model):
    __tablename__ = 'pa_kpi_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    level_id = db.Column('level_id', db.ForeignKey('pa_levels.id'))
    level = db.relationship(PALevel, uselist=False)
    kpi_id = db.Column(db.ForeignKey('pa_kpis.id'))
    kpi = db.relationship('PAKPI', backref=db.backref('pa_kpi_items'))
    goal = db.Column('goal', db.Text())

    def __str__(self):
        return f'{self.kpi.detail} เป้าคือ {self.goal} ({self.kpi.type}) ได้ {self.level} คะแนน'


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
    task = db.Column(db.Text())
    percentage = db.Column(db.Numeric())
    pa_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    pa = db.relationship('PAAgreement', backref=db.backref('pa_items', cascade='all, delete-orphan'))
    kpi_items = db.relationship('PAKPIItem', secondary=item_kpi_item_assoc_table)

    def __str__(self):
        return self.task


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

    def __str__(self):
        return self.staff.fullname


class PAScoreSheet(db.Model):
    __tablename__ = 'pa_score_sheets'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pa_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    pa = db.relationship('PAAgreement', backref=db.backref('pa_score_sheet', lazy='dynamic'), foreign_keys=[pa_id])
    committee_id = db.Column('committee_id', db.ForeignKey('pa_committees.id'))
    committee = db.relationship('PACommittee', backref=db.backref('committee_score_sheet'), foreign_keys=[committee_id])
    is_consolidated = db.Column('is_consolidated', db.Boolean(), default=False)
    is_final = db.Column('is_final', db.Boolean(), default=False)

    def get_score_sheet_item(self, pa_item_id, kpi_item_id):
        return self.score_sheet_items.filter_by(item_id=pa_item_id, kpi_item_id=kpi_item_id).first()


class PAScoreSheetItem(db.Model):
    __tablename__ = 'pa_score_sheet_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score_sheet_id = db.Column(db.ForeignKey('pa_score_sheets.id'))
    score_sheet = db.relationship('PAScoreSheet', backref=db.backref('score_sheet_items', lazy='dynamic',
                                                                     cascade='all, delete-orphan'))
    item_id = db.Column(db.ForeignKey('pa_items.id'))
    item = db.relationship('PAItem', backref=db.backref('pa_score_item'), foreign_keys=[item_id])
    kpi_item_id = db.Column(db.ForeignKey('pa_kpi_items.id'))
    kpi_item = db.relationship('PAKPIItem', backref=db.backref('sore_sheet_kpi_item'), foreign_keys=[kpi_item_id])
    score = db.Column('score', db.Numeric())
    comment = db.Column('comment', db.Text())

    @property
    def score_tag(self):
        return f'<div class="control"><div class="tags has-addons"><span class="tag">{self.score_sheet.committee.staff.fullname}</span><span class="tag is-info">{self.score}</span></div></div>'


class PAApprovedScoreSheet(db.Model):
    __tablename__ = 'pa_approved_score_sheets'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score_sheet_id = db.Column(db.ForeignKey('pa_score_sheets.id'))
    score_sheet = db.relationship('PAScoreSheet', backref=db.backref('approved_score_sheet'), foreign_keys=[score_sheet_id])
    committee_id = db.Column('committee_id', db.ForeignKey('pa_committees.id'))
    committee = db.relationship('PACommittee', backref=db.backref('committee_approved_score_sheet'), foreign_keys=[committee_id])
    approved_at = db.Column('approved_at', db.DateTime(timezone=True))
