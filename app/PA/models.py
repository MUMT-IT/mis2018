from app.main import db
from app.staff.models import StaffAccount

level_kpi_item_assoc = db.Table('level_kpi_item_assoc',
                                   db.Column('level_id', db.Integer, db.ForeignKey('pa_levels.id')),
                                   db.Column('kpi_item_id', db.Integer, db.ForeignKey('pa_kpi_items.id'))
                                   )

class PARound(db.Model):
    __tablename__ = 'pa_rounds'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start = db.Column('start', db.Date())
    end = db.Column('end', db.Date())


class PAAgreement(db.Model):
    __tablename__ = 'pa_agreements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('pa_agreements', cascade='all, delete-orphan'))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    round_id = db.Column('round_id', db.ForeignKey('pa_rounds.id'))
    round = db.relationship(PARound, backref=db.backref('agreements', lazy='dynamic'))


class PARequest(db.Model):
    __tablename__ = 'pa_requests'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pd_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    supervisor_id = db.Column('supervisor_id', db.ForeignKey('staff_account.id'))
    for_ = db.Column(db.String(), nullable=False, info={'label': 'สำหรับ',
                                                        'choices': [(c, c) for c in ('อนุมัติ', 'แก้ไข')]})
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


class PAKPI(db.Model):
    __tablename__ = 'pa_kpis'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pd_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    detail = db.Column(db.Text())
    type = db.Column(db.String(), info={'label': 'ประเภท',
                                        'choices': [(c, c) for c in ('ปริมาณ', 'คุณภาพ', 'เวลา', 'ความคุ้มค่า', 'ความพึงพอใจ')]})


class PAKPIItem(db.Model):
    __tablename__ = 'pa_kpi_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    level = db.relationship(PALevel, secondary=level_kpi_item_assoc)
    kpi_id = db.Column(db.ForeignKey('pa_kpis.id'))
    goal = db.Column('goal', db.Text())


class PAItem(db.Model):
    __tablename__ = 'pa_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task = db.Column(db.Text())
    percentage = db.Column(db.Numeric())


class PACommittee(db.Model):
    __tablename__ = 'pa_committees'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account_id = db.Column(db.ForeignKey('staff_account.id'))
    org_id = db.Column(db.ForeignKey('orgs.id'))
    round_id = db.Column(db.ForeignKey('pa_rounds.id'))
    role = db.Column('role', db.String(), info={'label': 'ประเภท',
                                                'choices': [(c, c) for c in ('ประธาน', 'เสนอชื่อโดยประธาน', 'เสนอจากผู้รับการประเมิน')]})


class PAScoreSheet(db.Model):
    __tablename__ = 'pa_score_sheets'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pd_id = db.Column('pa_id', db.ForeignKey('pa_agreements.id'))
    committee_id = db.Column('pa_committee_id', db.ForeignKey('pa_committees.id'))
    is_consolidated = db.Column('is_consolidated', db.Boolean(), default=False)


class PAScoreSheetItem(db.Model):
    __tablename__ = 'pa_score_sheet_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score_sheet_id = db.Column(db.ForeignKey('pa_score_sheets.id'))
    kpi_id = db.Column(db.ForeignKey('pa_kpis.id'))
    score = db.Column('score', db.Numeric())
    comment = db.Column('comment', db.Text())

