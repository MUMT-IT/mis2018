from pygments.lexer import default

from app.main import db
from app.models import Process, StrategyActivity
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


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
    type = db.Column('type', db.String(), info={'label': 'ประเภทคำขอ',
                                                'choices': [('None', 'กรุณาเลือกประเภทคำขอ'),
                                                            ('พัฒนาโปรแกรมใหม่', 'พัฒนาโปรแกรมใหม่'),
                                                            ('ปรับปรุงระบบที่มีอยู่', 'ปรับปรุงระบบที่มีอยู่')]})
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

    def __str__(self):
        return f'{self.title}'

    @property
    def num_open_issues(self):
        return len([issue for issue in self.issues.all() if issue.status != 'Closed'])

    @property
    def num_timelines(self):
        return len([timeline for timeline in self.timelines if timeline.status != 'ยกเลิกการพัฒนา' or timeline.status != 'เสร็จสิ้น'])

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'type': self.type,
            'description': self.description,
            'has_timeline': True if self.timelines else False,
            'created_by': self.created_by.fullname if self.created_by else None,
            'org': self.created_by.personal_info.org.name if self.created_by else None,
            'created_date': self.created_date,
            'status': self.status,
            'open_issues': self.num_open_issues,
            'num_timelines': self.num_timelines
        }


class SoftwareRequestTimeline(db.Model):
    __tablename__ = 'software_request_timelines'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    sequence = db.Column('sequence', db.String(), info={'label': 'ลำดับ'})
    task = db.Column('task', db.Text(), nullable=False, info={'label': 'Task'})
    start = db.Column('start', db.Date(), nullable=False, info={'label': 'วันที่เริ่มต้น'})
    estimate = db.Column('estimate', db.Date(), nullable=False, info={'label': 'วันที่คาดว่าจะแล้วเสร็จ'})
    phase = db.Column('phase', db.String(), nullable=False, info={'label': 'Phase',
                                                                  'choices': [('1', '1'),
                                                                              ('2', '2'),
                                                                              ('3', '3'),
                                                                              ('4', '4')
                                                                              ]})
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

    def __str__(self):
        return f'{self.phase}: {self.task}'


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
    issue = db.Column('issue', db.Text(), nullable=False, info={'label': 'Issue'})
    created_by = db.Column('created_by', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount)
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    closed_at = db.Column('closed_at', db.DateTime(timezone=True))
    accepted_at = db.Column('accepted_at', db.DateTime(timezone=True))

    @property
    def status(self):
        if self.cancelled_at:
            return 'Cancelled'
        elif self.closed_at:
            return 'Closed'
        elif self.accepted_at:
            return 'Working'
        else:
            return 'Draft'
