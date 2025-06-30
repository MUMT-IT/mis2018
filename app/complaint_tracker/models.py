# -*- coding:utf-8 -*-
import os
import boto3
from pytz import timezone
from sqlalchemy import func

from app.main import db
from app.models import CostCenter, IOCode
from app.procurement.models import ProcurementDetail
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount

AWS_ACCESS_KEY_ID = os.getenv('BUCKETEER_AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('BUCKETEER_AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('BUCKETEER_AWS_REGION')
S3_BUCKET_NAME = os.getenv('BUCKETEER_BUCKET_NAME')

s3 = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

localtz = timezone('Asia/Bangkok')


complaint_record_room_assoc = db.Table('complaint_record_room_assoc',
                                          db.Column('id', db.Integer, autoincrement=True, primary_key=True),
                                          db.Column('room_id', db.Integer, db.ForeignKey('scheduler_room_resources.id')),
                                          db.Column('record_id', db.Integer, db.ForeignKey('complaint_records.id'))
                                          )

complaint_record_procurement_assoc = db.Table('complaint_record_procurement_assoc',
                                              db.Column('id', db.Integer, autoincrement=True, primary_key=True),
                                              db.Column('procurement_id', db.Integer, db.ForeignKey('procurement_details.id')),
                                              db.Column('record_id', db.Integer, db.ForeignKey('complaint_records.id'))
                                              )

complaint_record_tag_assoc = db.Table('complaint_record_tag_assoc',
                                      db.Column('id', db.Integer, autoincrement=True, primary_key=True),
                                      db.Column('tag_id', db.Integer, db.ForeignKey('complaint_tags.id')),
                                      db.Column('record_id', db.Integer, db.ForeignKey('complaint_records.id'))
                                      )


class ComplaintCategory(db.Model):
    __tablename__ = 'complaint_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column('category', db.String(255), nullable=False)

    def __str__(self):
        return u'{}'.format(self.category)


class ComplaintTopic(db.Model):
    __tablename__ = 'complaint_topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(255), nullable=False)
    code = db.Column('code', db.String())
    category_id = db.Column('category_id', db.ForeignKey('complaint_categories.id'))
    category = db.relationship(ComplaintCategory, backref=db.backref('topics', cascade='all, delete-orphan'))

    def __str__(self):
        return u'{}'.format(self.topic)


class ComplaintSubTopic(db.Model):
    __tablename__ = 'complaint_sub_topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subtopic = db.Column('subtopic', db.String())
    topic_id = db.Column('topic_id', db.ForeignKey('complaint_topics.id'))
    topic = db.relationship(ComplaintTopic, backref=db.backref('subtopics', cascade='all, delete-orphan'))

    def __str__(self):
        return '{}'.format(self.subtopic)


class ComplaintAdmin(db.Model):
    __tablename__ = 'complaint_admins'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account = db.Column('staff_account', db.ForeignKey('staff_account.id'))
    is_supervisor = db.Column('is_supervisor', db.Boolean(), default=False)
    topic_id = db.Column('topic_id', db.ForeignKey('complaint_topics.id'))
    topic = db.relationship(ComplaintTopic, backref=db.backref('admins', cascade='all, delete-orphan'))
    admin = db.relationship(StaffAccount)

    def __str__(self):
        return u'{}'.format(self.admin.fullname)


class ComplaintPriority(db.Model):
    __tablename__ = 'complaint_priorities'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    priority = db.Column('priority', db.Integer, nullable=False)
    priority_text = db.Column('priority_text', db.String(255), nullable=False)
    priority_detail = db.Column('priority_detail', db.String)
    color = db.Column('color', db.String())

    def __str__(self):
        return u'{}'.format(self.priority_text)


class ComplaintStatus(db.Model):
    __tablename__ = 'complaint_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    status = db.Column('status', db.String(), nullable=False)
    code = db.Column('code', db.String())
    icon = db.Column('icon', db.String())
    color = db.Column('color', db.String())

    def __str__(self):
        return u'{}'.format(self.status)


class ComplaintTag(db.Model):
    __tablename__ = 'complaint_tags'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    tag = db.Column('tag', db.String(), info={'label': 'แท็กเรื่อง'})

    def __str__(self):
        return self.tag


class ComplaintType(db.Model):
    __tablename__ = 'complaint_types'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    type = db.Column('type', db.String(), info={'label': 'ประเภท'})

    def __str__(self):
        return self.type


class ComplaintRecord(db.Model):
    __tablename__ = 'complaint_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    desc = db.Column('desc', db.Text(), nullable=False, info={'label': u'รายละเอียด'})
    appeal = db.Column('appeal', db.Boolean(), default=False, info={'label': 'ร้องเรียน'})
    channel_receive = db.Column('channel_receive', db.String(), info={'label': 'ช่องทางรับเรื่อง',
                                                                      'choices': [('None', 'กรุณาเลือกช่องทางรับเรื่อง'),
                                                                                  ('Website ของคณะเทคนิคการแพทย์', 'Website ของคณะเทคนิคการแพทย์'),
                                                                                  ('QR Code', 'QR Code'),
                                                                                  ('จดหมาย/Email ถึงคณบดีคณะเทคนิคการแพทย์', 'จดหมาย/Email ถึงคณบดีคณะเทคนิคการแพทย์'),
                                                                                  ('Walk in ที่คณะเทคนิคการแพทย์', 'Walk in ที่คณะเทคนิคการแพทย์'),
                                                                                  ('ทางโทรศัพท์', 'ทางโทรศัพท์')
                                                                                  ]})
    fl_name = db.Column('fl_name', db.String(), info={'label': 'ชื่อ-นามสกุล'})
    telephone = db.Column('telephone', db.String(), info={'label': 'เบอร์โทรศัพท์'})
    email = db.Column('email', db.String(), info={'label': 'อีเมล'})
    is_contact = db.Column('is_contact', db.Boolean(), default=False, info={'label': 'ต้องการให้ติดต่อกลับ'})
    deadline = db.Column('deadline', db.DateTime(timezone=True), info={'label': 'deadline'})
    topic_id = db.Column('topic_id', db.ForeignKey('complaint_topics.id'))
    topic = db.relationship(ComplaintTopic, backref=db.backref('records', cascade='all, delete-orphan'))
    subtopic_id = db.Column('subtopic_id', db.ForeignKey('complaint_sub_topics.id'))
    subtopic = db.relationship(ComplaintSubTopic, backref=db.backref('records', cascade='all, delete-orphan'))
    priority_id = db.Column('priority_id', db.ForeignKey('complaint_priorities.id'))
    priority = db.relationship(ComplaintPriority, backref=db.backref('records', cascade='all, delete-orphan'))
    status_id = db.Column('status', db.ForeignKey('complaint_statuses.id'))
    status = db.relationship(ComplaintStatus, backref=db.backref('records', cascade='all, delete-orphan'))
    type_id = db.Column('type_id', db.ForeignKey('complaint_types.id'))
    type = db.relationship(ComplaintType, backref=db.backref('records', cascade='all, delete-orphan'))
    origin_id = db.Column('origin_id', db.ForeignKey('complaint_records.id'))
    children = db.relationship('ComplaintRecord', backref=db.backref('parent', remote_side=[id]))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    closed_at = db.Column('closed_at', db.DateTime(timezone=True))
    tags = db.relationship(ComplaintTag, secondary=complaint_record_tag_assoc, backref=db.backref('records'))
    room_id = db.Column('room_id', db.ForeignKey('scheduler_room_resources.id'))
    room = db.relationship(RoomResource, foreign_keys=[room_id], backref=db.backref('complaints'))
    procurement_location_id = db.Column('procurement_location_id', db.ForeignKey('scheduler_room_resources.id'))
    procurement_location = db.relationship(RoomResource, foreign_keys=[procurement_location_id])
    rooms = db.relationship(RoomResource, secondary=complaint_record_room_assoc, backref=db.backref('complaint_records'))
    procurements = db.relationship(ProcurementDetail, secondary=complaint_record_procurement_assoc,
                                   backref=db.backref('complaint_records'))
    complainant_id = db.Column('complainant_id', db.ForeignKey('staff_account.id'))
    complainant = db.relationship(StaffAccount, backref=db.backref('my_complaints', lazy='dynamic'))
    file_name = db.Column('file_name', db.String(255))
    url = db.Column('url', db.String(255))

    @property
    def is_editable(self):
        return self.closed_at is None

    @property
    def to_link(self):
        return self.generate_presigned_url(s3, S3_BUCKET_NAME)

    def generate_presigned_url(self):

        if self.url:
            try:
                return s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': S3_BUCKET_NAME, 'Key': self.url},
                    ExpiresIn=3600
                )
            except Exception as e:
                print(f"Error generating presigned URL: {e}")
                return None
        return None

    def has_assignee(self, admin_id):
        for assignee in self.assignees:
            if assignee.assignee_id == admin_id:
                return True
        return False

    def has_admin(self, admin):
        for topic in self.topic.admins:
            if topic.admin == admin:
                return True
        return False

    def get_record_by_status(self, status):
        if self.status and self.status.code == status:
                return self
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at.astimezone(localtz).isoformat(),
            'topic': self.topic.topic,
            'type': self.type.type if self.type else 'ไม่ระบุ',
            'priority': self.priority.priority_text if self.priority else None,
            'desc': self.desc,
            'status': self.status.status if self.status else None,
            'procurement':  [procurement.category.category if procurement.category else 'ไม่ระบุ' for procurement in self.procurements] if self.procurements else 'ไม่ระบุ'
        }


class ComplaintActionRecord(db.Model):
    __tablename__ = 'complaint_action_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('comments', cascade='all, delete-orphan'))
    reviewer_id = db.Column('reviewer_id', db.ForeignKey('complaint_admins.id'))
    reviewer = db.relationship(ComplaintAdmin, backref=db.backref('comments', cascade='all, delete-orphan'),
                               foreign_keys=[reviewer_id])
    review_comment = db.Column('review_comment', db.Text(), info={'label': u'บันทึกจากผู้รีวิว'})
    comment_datetime = db.Column('comment_datetime', db.DateTime(timezone=True), server_default=func.now())
    approver_id = db.Column('approver_id', db.ForeignKey('complaint_admins.id'))
    approver = db.relationship(ComplaintAdmin, foreign_keys=[approver_id])
    approved = db.Column('approved', db.DateTime(timezone=True))
    approver_comment = db.Column('approver_comment', db.Text())
    deadline = db.Column('deadline', db.DateTime(timezone=True))


class ComplaintPerformanceReport(db.Model):
    __tablename__ = 'complaint_performance_reports'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('reports', cascade='all, delete-orphan'))
    report_comment = db.Column('report_comment', db.Text(), info={'label': 'รายงานผลการดำเนินงาน'})
    report_datetime = db.Column('report_datetime', db.DateTime(timezone=True))
    reporter_id = db.Column('reporter_id', db.ForeignKey('complaint_admins.id'))
    reporter = db.relationship(ComplaintAdmin, backref=db.backref('reports', cascade='all, delete-orphan'))


class ComplaintAssignee(db.Model):
    __tablename__ = 'complaint_assignees'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('assignees', cascade='all, delete-orphan'))
    assignee_id = db.Column('assignee_id', db.ForeignKey('complaint_admins.id'))
    assignee = db.relationship(ComplaintAdmin, backref=db.backref('records', cascade='all, delete-orphan'))
    assignee_datetime = db.Column('assignee_datetime', db.DateTime(timezone=True))


class ComplaintHandler(db.Model):
    __tablename__ = 'complaint_handlers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('handlers', cascade='all, delete-orphan'))
    handler_id = db.Column('handler_id', db.ForeignKey('complaint_admins.id'))
    handler = db.relationship(ComplaintAdmin, backref=db.backref('handled_records', cascade='all, delete-orphan'))
    handled_at = db.Column('handled_at', db.DateTime(timezone=True))


class ComplaintInvestigator(db.Model):
    __tablename__ = 'complaint_investigators'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inviter_id = db.Column('inviter_id', db.ForeignKey('staff_account.id'))
    inviter = db.relationship(StaffAccount, backref=db.backref('investigators', cascade='all, delete-orphan'))
    admin_id = db.Column('admin_id', db.ForeignKey('complaint_admins.id'))
    admin = db.relationship(ComplaintAdmin, backref=db.backref('investigators', cascade='all, delete-orphan'))
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('investigators', cascade='all, delete-orphan'))

    def get_record_by_status(self, status):
        if self.record.status and self.record.status.code == status:
            return self.record
        return None


class ComplaintAdminTypeAssociation(db.Model):
    __tablename__ = 'complaint_admin_type_associations'
    type_id = db.Column(db.ForeignKey('complaint_types.id'), primary_key=True)
    type = db.relationship(ComplaintType, backref=db.backref('admins', cascade='all, delete-orphan'))
    admin_id = db.Column(db.ForeignKey('complaint_admins.id'), primary_key=True)
    admin = db.relationship(ComplaintAdmin, backref=db.backref('types', cascade='all, delete-orphan'))


class ComplaintCoordinator(db.Model):
    __tablename__ = 'complaint_coordinators'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coordinator_id = db.Column('coordinator_id', db.ForeignKey('staff_account.id'))
    coordinator = db.relationship(StaffAccount, backref=db.backref('coordinators', cascade='all, delete-orphan'),
                                  foreign_keys=[coordinator_id])
    note = db.Column('note', db.Text(), info={'label': 'รายงานผลการดำเนินงาน'})
    received_datetime = db.Column('received_datetime', db.DateTime(timezone=True))
    submitted_datetime = db.Column('submitted_datetime', db.DateTime(timezone=True))
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('coordinators', cascade='all, delete-orphan'))
    recorder_id = db.Column('recorder_id', db.ForeignKey('staff_account.id'))
    recorder = db.relationship(StaffAccount, foreign_keys=[recorder_id])

    def get_record_by_status(self, status):
        if self.record.status and self.record.status.code == status:
            return self.record
        return None


class ComplaintRepairApproval(db.Model):
    __tablename__ = 'complaint_repair_approvals'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mhesi_no = db.Column('mhesi_no', db.String(), info={'label': 'ที่'})
    procurement_no = db.Column('procurement_no', db.String(), info={'label': 'เลขครุภัณฑ์'})
    repair_type = db.Column('repair_type', db.String(), info={'label': 'ประเภทอนุมัติหลักการซ่อม',
                                                                  'choices': [('เร่งด่วน', 'เร่งด่วน'),
                                                                              ('ไม่เร่งด่วน (จ้าง/ซ่อม)', 'ไม่เร่งด่วน (จ้าง/ซ่อม)'),
                                                                              ('ไม่เร่งด่วน (จ้างซ่อม)', 'ไม่เร่งด่วน (จ้างซ่อม)')
                                                                              ]
                                                                  })
    principle_approval_type = db.Column('principle_approval_type', db.String(), info={'label': 'ประเภทการขออนุมัติ',
                                                                                      'choices': [('ซื้อ', 'ซื้อ'),
                                                                                                  ('จ้าง', 'จ้าง')
                                                                                                  ]
                                                                                      })
    created_at = db.Column('created_at', db.DateTime(timezone=True), info={'label': 'วันที่'})
    # requester_id = db.Column('requester_id', db.ForeignKey('staff_account.id'))
    # requester = db.relationship(StaffAccount, backref=db.backref('repair_requests', cascade='all, delete-orphan'),
    #                             foreign_keys=[requester_id])
    position = db.Column('position', db.String(), info={'label': 'ตำแหน่ง'})
    organization = db.Column('organization', db.String(), info={'label': 'ภาควิชา/ศูนย์/หน่วยงาน'})
    item = db.Column('item', db.String())
    reason = db.Column('reason', db.Text())
    detail = db.Column('detail', db.Text())
    purpose = db.Column('purpose', db.Text())
    price = db.Column('price', db.Float())
    budget_source = db.Column('budget_source', db.String())
    book_number = db.Column('book_number', db.String(), info={'label': 'เล่มที่'})
    receipt_number = db.Column('receipt_number', db.String(), info={'label': 'เลขที่'})
    receipt_date = db.Column('receipt_date', db.Date(), info={'label': 'วันที่'})
    purchase_type = db.Column('purchase_type', db.String(), info={'label': 'ประเภทการซื้อ',
                                                                  'choices': [('รายได้ส่วนงาน', 'รายได้ส่วนงาน'),
                                                                              ('เงินงบประมาณแผ่นดิน', 'เงินงบประมาณแผ่นดิน')
                                                                              ]
                                                                  })
    budget_year = db.Column('budget_year', db.Integer(), info={'label': 'ประจำปีงบประมาณ'})
    cost_center_id = db.Column('cost_center_id', db.ForeignKey('cost_centers.id'))
    cost_center = db.relationship(CostCenter, backref=db.backref('repair_approvals'))
    io_code_id = db.Column('io_code_id', db.ForeignKey('iocodes.id'))
    io_code = db.relationship(IOCode, backref=db.backref('repair_approvals'))
    product = db.Column('product', db.String(), info={'label': 'ผลผลิต'})
    remark = db.Column('remark', db.Text())
    borrower_id = db.Column('borrower_id', db.ForeignKey('staff_account.id'))
    borrower = db.relationship(StaffAccount, backref=db.backref('borrowed_repairs'),
                              foreign_keys=[borrower_id])
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount, backref=db.backref('repair_approvals'),
                              foreign_keys=[creator_id])
    record_id = db.Column('record_id', db.ForeignKey('complaint_records.id'))
    record = db.relationship(ComplaintRecord, backref=db.backref('repair_approvals'))

    def __str__(self):
        return self.item


class ComplaintCommittee(db.Model):
    __tablename__ = 'complaint_committees'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    committee_name = db.Column('committee_name', db.String())
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('committees'))
    position = db.Column('position', db.String(), info={'label': 'ตำแหน่ง'})
    committee_position = db.Column('committee_position', db.String(), info={'label': 'ตำแหน่งคณะกรรมการ',
                                                                            'choices': [('ประธานกรรมการ', 'ประธานกรรมการ'),
                                                                                        ('กรรมการ', 'กรรมการ'),
                                                                                        ('ผู้ตรวจรับพัสดุ', 'ผู้ตรวจรับพัสดุ')
                                                                                        ]
                                                                            })
    repair_approval_id = db.Column('record_id', db.ForeignKey('complaint_repair_approvals.id'))
    repair_approval = db.relationship(ComplaintRepairApproval, backref=db.backref('committees', cascade='all, delete-orphan'))