from app.main import db
from app.staff.models import StaffAccount


class SoftwareRequestDetail(db.Model):
    __tablename__ = 'software_request_details'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), nullable=False, info={'label': 'หัวข้อคำขอ'})
    description = db.Column('description', db.Text(), info={'label': 'รายละเอียดคำขอ'})
    status = db.Column('status', db.String())
    type = db.Column('type', db.String(), info={'label': 'ประเภทคำขอ',
                                                'choices': [('None', 'กรุณาเลือกประเภทคำขอ'),
                                                            ('พัฒนาโปรแกรมใหม่', 'พัฒนาโปรแกรมใหม่'),
                                                            ('ปรับปรุงระบบที่มีอยู่', 'ปรับปรุงระบบที่มีอยู่')]})
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
    approve_comment = db.Column('approve_comment', db.Text(), info={'label': 'ความเห็นผู้อนุมัติ'})
    created_date = db.Column('created_date', db.DateTime(timezone=True))
    updated_date = db.Column('updated_date', db.DateTime(timezone=True))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship(StaffAccount, backref=db.backref('approve_requests'), foreign_keys=[approver_id])
    created_id = db.Column('created_id', db.ForeignKey('staff_account.id'))
    created_by = db.relationship(StaffAccount, backref=db.backref('created_requests'), foreign_keys=[created_id])
