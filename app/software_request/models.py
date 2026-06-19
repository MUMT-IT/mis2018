from pygments.lexer import default

from app.main import db
from app.models import Process, StrategyActivity
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


software_request_admin_assoc = db.Table('software_request_admin_assoc',
                                          db.Column('id', db.Integer, autoincrement=True, primary_key=True),
                                          db.Column('staff_id', db.Integer, db.ForeignKey('staff_account.id')),
                                          db.Column('request_id', db.Integer, db.ForeignKey('software_request_details.id')),
                                          )


class SoftwareRequestNumberID(db.Model):
    __tablename__ = 'software_request_number_ids'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    code = db.Column('code', db.String(), nullable=False)
    software_request = db.Column('software_request', db.String(), nullable=False)
    count = db.Column('count', db.Integer, default=0)

    def next(self):
        return u'{}'.format(self.count + 1)

    @classmethod
    def get_number(cls, code, db, software_request):
        number = cls.query.filter_by(code=code, software_request=software_request).first()
        if not number:
            number = cls(code=code, software_request=software_request, count=0)
            db.session.add(number)
            db.session.commit()
        return number

    @property
    def number(self):
        return u'{}'.format(self.count + 1)


class SoftwareRequestPhase(db.Model):
    __tablename__ = 'software_request_phases'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    phase = db.Column('phase', db.String(), nullable=False)

    def __str__(self):
        return f'{self.phase}'


class SoftwareRequestSystem(db.Model):
    __tablename__ = 'software_request_systems'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    system = db.Column('system', db.String())

    def __str__(self):
        return f'{self.system}'


class SoftwareRequestDetail(db.Model):
    __tablename__ = 'software_request_details'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), info={'label': 'หัวข้อคำขอ'})
    description = db.Column('description', db.Text(), info={'label': 'รายละเอียดคำขอ'})
    status = db.Column('status', db.String())
    note = db.Column('note', db.Text())
    type = db.Column('type', db.String(), info={'label': 'ประเภทคำขอ',
                                                'choices': [('', 'กรุณาเลือกประเภทคำขอ'),
                                                            ('พัฒนาโปรแกรมใหม่', 'พัฒนาโปรแกรมใหม่'),
                                                            ('ปรับปรุงระบบที่มีอยู่', 'ปรับปรุงระบบที่มีอยู่')]})
    system_id = db.Column('system_id', db.ForeignKey('software_request_systems.id'))
    system = db.relationship(SoftwareRequestSystem, backref=db.backref('software_requests'))
    work_process_id = db.Column('work_process_id', db.ForeignKey('db_processes.id'))
    work_process = db.relationship(Process, backref=db.backref('software_requests'))
    activity_id = db.Column('activity_id', db.ForeignKey('strategy_activities.id'))
    activity = db.relationship(StrategyActivity, backref=db.backref('software_requests', cascade='all, delete-orphan'))
    priority = db.Column('priority', db.String(), info={'label': 'ระดับความสำคัญ',
                                                        'choices': [('None', 'กรุณาเลือกระดับความสำคัญ'),
                                                                    ('สูง', 'สูง'),
                                                                    ('กลาง', 'กลาง'),
                                                                    ('ต่ำ', 'ต่ำ')
                                                                    ]})
    frequency = db.Column('frequency', db.String(), info={'label': 'ความถี่การใช้งาน',
                                                          'choices': [('None', 'กรุณาเลือกความถี่การใช้งาน'),
                                                                      ('รายวัน', 'รายวัน'),
                                                                      ('รายสัปดาห์', 'รายสัปดาห์'),
                                                                      ('รายเดือน', 'รายเดือน'),
                                                                      ('เป็นครั้งคราว', 'เป็นครั้งคราว'),
                                                                      ('ใช้ครั้งเดียว'), ('ใช้ครั้งเดียว')]})
    user_group = db.Column('user_group', db.String(), info={'label': 'กลุ่มผู้ใช้งาน',
                                                            'choices': [('หน่วยงานภายใน', ' หน่วยงานภายใน'),
                                                                        ('หน่วยงานภายนอก', 'หน่วยงานภายนอก'),
                                                                        ('บุคคลทั่วไป', ' บุคคลทั่วไป'),
                                                                        ('คู่ค้า', ' คู่ค้า'),
                                                                        ('นักศึกษา', 'นักศึกษา')]})
    required_information = db.Column('required_information', db.Text())
    suggestion = db.Column('suggestion', db.Text())
    reason = db.Column('reason', db.Text())
    appointment_date = db.Column('appointment_date', db.DateTime(timezone=True), info={'label': 'วันนัดหมาย'})
    room_id = db.Column('room_id', db.ForeignKey('scheduler_room_resources.id'))
    room = db.relationship(RoomResource, backref=db.backref('software_requests'))
    file_name = db.Column('file_name', db.String(255))
    url = db.Column('url', db.String(255))
    created_date = db.Column('created_date', db.DateTime(timezone=True))
    updated_date = db.Column('updated_date', db.DateTime(timezone=True))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship(StaffAccount, backref=db.backref('approve_requests'), foreign_keys=[approver_id])
    created_id = db.Column('created_id', db.ForeignKey('staff_account.id'))
    created_by = db.relationship(StaffAccount, backref=db.backref('created_requests'), foreign_keys=[created_id])
    staffs = db.relationship(StaffAccount, secondary=software_request_admin_assoc,
                             backref=db.backref('software_request_admins', lazy='dynamic'))

    def __str__(self):
        return f'{self.title}'

    @property
    def num_open_issues(self):
        return len([issue for issue in self.issues.all() if issue.status != 'Closed'])

    @property
    def num_timelines(self):
        return len([timeline for timeline in self.timelines if timeline.status != 'ยกเลิกการพัฒนา' and timeline.status != 'เสร็จสิ้น'])

    @property
    def status_color(self):
        if self.status == 'ส่งคำขอแล้ว':
            return 'is-link'
        elif self.status == 'อยู่ระหว่างพิจารณา':
            return 'is-warning'
        elif self.status == 'อนุมัติ':
            return 'is-success'
        elif self.status == 'เสร็จสิ้น':
            return 'is-info'
        elif self.status == 'ไม่อนุมัติ':
            return 'is-danger'
        else:
            return 'is-dark'

    @property
    def status_icon(self):
        if self.status == 'ส่งคำขอแล้ว':
            return '<i class="fas fa-hourglass-half"></i>'
        elif self.status == 'อยู่ระหว่างพิจารณา':
            return '<i class="fas fa-history"></i>'
        elif self.status == 'อนุมัติ':
            return '<i class="fas fa-pen-fancy"></i>'
        elif self.status == 'เสร็จสิ้น':
            return '<i class="fas fa-check"></i>'
        elif self.status == 'ไม่อนุมัติ':
            return '<i class="fas fa-times"></i>'
        else:
            return '<i class="fas fa-ban"></i>'

    @property
    def workflow_status(self):
        draft = all(not issue.tested_at
                    and not issue.closed_at
                    and not issue.accepted_at
                    for issue in self.issues) if self.issues else False
        working = any(issue.accepted_at for issue in self.issues) if self.issues else False
        testing = any(issue.tested_at for issue in self.issues) if self.issues else False

        if self.status == 'อนุมัติ':
            if not self.issues or draft:
                return 'ยังไม่ดำเนินการ'
            elif working:
                return 'กำลังพัฒนา'
            elif testing:
                return 'รอทดสอบ'
            else:
                return 'รอปิดโครงการ'
        else:
            if self.status == 'ส่งคำขอแล้ว':
                return 'รอดำเนินการ'
            else:
                return self.status

    @property
    def workflow_status_color(self):
        draft = all(not issue.tested_at
                    and not issue.closed_at
                    and not issue.accepted_at
                    for issue in self.issues) if self.issues else False
        working = any(issue.accepted_at for issue in self.issues) if self.issues else False
        testing = any(issue.tested_at for issue in self.issues) if self.issues else False

        if self.status == 'อนุมัติ':
            if not self.issues or draft:
                return 'is-danger'
            elif working:
                return 'is-warning'
            elif testing:
                return 'is-primary'
            else:
                return 'is-info'
        else:
            return self.status_color

    @property
    def workflow_status_icon(self):
        draft = all(not issue.tested_at
                    and not issue.closed_at
                    and not issue.accepted_at
                    for issue in self.issues) if self.issues else False
        working = any(issue.accepted_at for issue in self.issues) if self.issues else False
        testing = any(issue.tested_at for issue in self.issues) if self.issues else False

        if self.status == 'อนุมัติ':
            if not self.issues or draft:
                return '<i class="fas fa-ban"></i>'
            elif working:
                return '<i class="fas fa-hourglass-start"></i>'
            elif testing:
                return '<i class="fas fa-history"></i>'
            else:
                return '<i class="far fa-clock"></i>'
        else:
            return self.status_icon

    def to_dict(self, open_issues=None, num_timelines=None, has_timeline=None):
        # Allow precomputed counts from the admin listing query to avoid per-row lazy loads.
        open_issues = self.num_open_issues if open_issues is None else open_issues
        num_timelines = self.num_timelines if num_timelines is None else num_timelines
        has_timeline = bool(self.timelines) if has_timeline is None else has_timeline
        return {
            'id': self.id,
            'title': self.title,
            'type': self.type,
            'description': self.description,
            'has_timeline': has_timeline,
            'created_by': self.created_by.fullname if self.created_by else None,
            'org': self.created_by.personal_info.org.name if self.created_by else None,
            'created_date': self.created_date,
            'status': self.status,
            'workflow_status': self.workflow_status,
            'workflow_status_color': self.workflow_status_color,
            'workflow_status_icon': self.workflow_status_icon,
            'open_issues': open_issues,
            'num_timelines': num_timelines
        }


class SoftwareRequestTimeline(db.Model):
    __tablename__ = 'software_request_timelines'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sequence = db.Column('sequence', db.String(), info={'label': 'ลำดับ'})
    task = db.Column('task', db.Text(), nullable=False, info={'label': 'Task'})
    start = db.Column('start', db.Date(), nullable=False, info={'label': 'วันที่เริ่มต้น'})
    estimate = db.Column('estimate', db.Date(), nullable=False, info={'label': 'วันที่คาดว่าจะแล้วเสร็จ'})
    status = db.Column('status', db.String(), nullable=False,  info={'label': 'สถานะ',
                                                                     'choices': [('รอดำเนินการ', 'รอดำเนินการ'),
                                                                                 ('เสร็จสิ้น', 'เสร็จสิ้น'),
                                                                                 ('ยกเลิกการพัฒนา', 'ยกเลิกการพัฒนา')
                                                                                 ]})
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    admin_id = db.Column('admin_id', db.ForeignKey('staff_account.id'))
    admin = db.relationship(StaffAccount, backref=db.backref('request_timelines'))
    request_id = db.Column('request_id', db.ForeignKey('software_request_details.id'))
    request = db.relationship(SoftwareRequestDetail, backref=db.backref('timelines', cascade='all, delete-orphan'))
    issue_id = db.Column('issue_id', db.ForeignKey('software_issues.id'))
    issue = db.relationship('SoftwareIssues', backref=db.backref('timelines', lazy='dynamic'))

    def __str__(self):
        return self.task

    @property
    def status_color(self):
        if self.status == 'เสร็จสิ้น':
            return 'is-success'
        elif self.status == 'รอดำเนินการ':
            return 'is-info'
        else:
            return 'is-danger'


class SoftwareIssues(db.Model):
    __tablename__ = 'software_issues'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    software_request_detail_id = db.Column('software_request_detail_id',
                                           db.ForeignKey('software_request_details.id'))
    software_request_detail = db.relationship(SoftwareRequestDetail, backref=db.backref('issues', lazy='dynamic'))
    label = db.Column('label', db.String(), nullable=False, info={
        'label': 'ประเภท',
        'choices': [(c,c) for c in ('Bug', 'Request', 'Enhancement')],
    })
    issue = db.Column('issue', db.Text(), nullable=False, info={'label': 'Issue/Request'})
    deadline = db.Column('deadline', db.Date(), info={'label': 'Deadline'})
    phase_id = db.Column('phase_id', db.ForeignKey('software_request_phases.id'))
    phase = db.relationship(SoftwareRequestPhase, backref=db.backref('software_request_issues'))
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, foreign_keys=[created_by])
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_by = db.Column('updated_by', db.ForeignKey('staff_account.id'))
    updater = db.relationship(StaffAccount, foreign_keys=[updated_by])
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    tested_at = db.Column('tested_at', db.DateTime(timezone=True))
    closed_at = db.Column('closed_at', db.DateTime(timezone=True))
    accepted_at = db.Column('accepted_at', db.DateTime(timezone=True))
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('software_request_issues'), foreign_keys=[staff_id])

    def __str__(self):
        return self.issue

    @property
    def status(self):
        if self.cancelled_at:
            return 'Cancelled'
        elif self.closed_at:
            return 'Closed'
        elif self.accepted_at:
            return 'Working'
        elif self.tested_at:
            return 'Testing'
        else:
            return 'Draft'

    @property
    def status_color(self):
        if self.cancelled_at:
            return 'is-danger'
        elif self.closed_at:
            return 'is-dark'
        elif self.accepted_at:
            return 'is-success'
        elif self.tested_at:
            return 'is-warning'
        else:
            return 'is-info'

#
class SoftwareRequestTestResult(db.Model):
    __tablename__ = 'software_request_test_results'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    status = db.Column('status', db.String())
    note = db.Column('note', db.Text())
    issue_id = db.Column('issue_id', db.ForeignKey('software_issues.id'))
    issue = db.relationship(SoftwareIssues, backref=db.backref('test_results'))
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    recorded_at = db.Column('recorded_at', db.DateTime(timezone=True))
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('created_test_results'), foreign_keys=[creator_id])
    updater_id = db.Column('updater_id', db.ForeignKey('staff_account.id'))
    updater = db.relationship(StaffAccount, backref=db.backref('updated_test_results'), foreign_keys=[updater_id])
    recorder_id = db.Column('recorder_id', db.ForeignKey('staff_account.id'))
    recorder = db.relationship(StaffAccount, backref=db.backref('recorded_test_results'), foreign_keys=[recorder_id])
    request_id = db.Column('request_id', db.ForeignKey('software_request_details.id'))
    request = db.relationship(SoftwareRequestDetail, backref=db.backref('test_results'))

    def __str__(self):
        return self.issue.issue if self.issue else ''

    @property
    def status_color(self):
        if self.status == 'ผ่าน':
            return 'is-success'
        else:
            return 'is-danger'


# BDD traceability objects are kept separate from SoftwareRequestDetail so the
# legacy request workflow stays unchanged while we add AI-assisted feature
# generation and test execution history.
class BDDFeature(db.Model):
    __tablename__ = 'bdd_features'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    software_request_id = db.Column(
        'software_request_id',
        db.ForeignKey('software_request_details.id'),
        index=True,
        nullable=False,
    )
    software_request = db.relationship(
        SoftwareRequestDetail,
        backref=db.backref('bdd_features', cascade='all, delete-orphan'),
    )
    feature_title = db.Column('feature_title', db.String(), nullable=False)
    gherkin_text = db.Column('gherkin_text', db.Text(), nullable=False)
    feature_file_path = db.Column('feature_file_path', db.String(), nullable=True)
    generated_by_ai = db.Column('generated_by_ai', db.Boolean(), nullable=False, default=False)
    reviewed_by_human = db.Column('reviewed_by_human', db.Boolean(), nullable=False, default=False)
    version = db.Column('version', db.Integer(), nullable=False, default=1)
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))

    def __repr__(self):
        return f'<BDDFeature id={self.id} title={self.feature_title!r}>'


class BDDTestRun(db.Model):
    __tablename__ = 'bdd_test_runs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    bdd_feature_id = db.Column(
        'bdd_feature_id',
        db.ForeignKey('bdd_features.id'),
        index=True,
        nullable=False,
    )
    bdd_feature = db.relationship(
        BDDFeature,
        backref=db.backref('bdd_test_runs', cascade='all, delete-orphan'),
    )
    status = db.Column('status', db.String(), nullable=False, index=True)
    scenario_count = db.Column('scenario_count', db.Integer(), nullable=False, default=0)
    passed_count = db.Column('passed_count', db.Integer(), nullable=False, default=0)
    failed_count = db.Column('failed_count', db.Integer(), nullable=False, default=0)
    undefined_count = db.Column('undefined_count', db.Integer(), nullable=False, default=0)
    executed_by = db.Column('executed_by', db.String(), nullable=False)
    report_path = db.Column('report_path', db.String(), nullable=True)
    executed_at = db.Column('executed_at', db.DateTime(timezone=True), index=True)

    def __repr__(self):
        return f'<BDDTestRun id={self.id} status={self.status!r}>'
