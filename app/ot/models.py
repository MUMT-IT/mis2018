# -*- coding:utf-8 -*-

from ..main import db
from pytz import timezone
from app.models import Org
from app.staff.models import StaffAccount
from datetime import datetime


ot_announce_document_assoc_table = db.Table('ot_announce_document_assoc',
                                         db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'),
                                                   primary_key=True),
                                         db.Column('document_id', db.ForeignKey('ot_document_approval.id'),
                                                   primary_key=True),
                                         )


ot_staff_assoc_table = db.Table('ot_staff_assoc',
                                db.Column('staff_id', db.ForeignKey('staff_account.id'),
                                          primary_key=True),
                                db.Column('document_id', db.ForeignKey('ot_document_approval.id'),
                                          primary_key=True),
                                )


class OtPaymentAnnounce(db.Model):
    __tablename__ = 'ot_payment_announce'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(), info={'label': u'เรื่อง'})
    file_name = db.Column('file_name', db.String())
    upload_file_url = db.Column('upload_file_url', db.String())
    created_account_id = db.Column('created_account_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('ot_announcement'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=datetime.now())
    announce_at = db.Column('announce_at', db.DateTime(timezone=True), info={'label': u'ประกาศเมื่อ'})
    start_datetime = db.Column('start_datetime', db.DateTime(timezone=True), info={'label': u'เริ่มใช้ตั้งแต่'})
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))

    def __str__(self):
        return self.topic


class OtCompensationRate(db.Model):
    __tablename__ = 'ot_compensation_rate'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    announce_id = db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'))
    announcement = db.relationship(OtPaymentAnnounce, backref=db.backref('ot_rate'))
    work_at_org_id = db.Column('work_at_org_id', db.ForeignKey('orgs.id') )
    work_for_org_id = db.Column('work_for_org_id', db.ForeignKey('orgs.id'))
    work_at_org = db.relationship(Org, backref=db.backref('ot_work_at_rate'), foreign_keys=[work_at_org_id])
    work_for_org = db.relationship(Org, backref=db.backref('ot_work_for_rate'), foreign_keys=[work_for_org_id])
    role = db.Column('role', db.String(), info={'label': u'ตำแหน่ง'})
    start_time = db.Column('start_time', db.Time(), info={'label': u'เวลาเริ่มต้น'})
    end_time = db.Column('end_time', db.Time(), info={'label': u'เวลาสิ้นสุด'})
    per_period = db.Column('per_period', db.Integer(), info={'label': u'ต่อคาบ'})
    per_hour = db.Column('per_hour', db.Integer(), info={'label': u'ต่อชั่วโมง'})
    per_day = db.Column('per_day', db.Integer(), info={'label': u'ต่อวัน'})
    is_faculty_emp = db.Column('is_faculty_emp', db.Boolean(), info={'label': u'บุคลากรสังกัดคณะ'})
    is_workday = db.Column('is_workday', db.Boolean(), default=True, nullable=False, info={'label': u'นอกเวลาราชการ'})
    max_hour = db.Column('max_hour', db.Integer(), info={'label': u'จำนวนชั่วโมงสูงสุดที่สามารถทำได้'})
    double_payment = db.Column('double_payment', db.Boolean(), default=True, nullable=False,
                               info={'label': u'เบิกซ้ำกับอันอื่นได้'})
    is_role_required = db.Column('is_role_required', db.Boolean(), info={'label': u'จำเป็นต้องระบุรายละเอียดตำแหน่ง'})

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'announcement': self.announcement.topic,
            'work_at_org': self.work_at_org.name,
            'work_for_org': self.work_for_org.name,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time is not None else "",
            'end_time': self.end_time.strftime('%H:%M') if self.end_time is not None else "",
            'per_period': self.per_period,
            'per_hour': self.per_hour,
            'per_day': self.per_day,
            'is_workday': self.is_workday,
            'is_role_required': self.is_role_required,
        }


class OtDocumentApproval(db.Model):
    __tablename__ = 'ot_document_approval'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), info={'label': u'เรื่อง'})
    approval_no = db.Column('approval_no', db.String(), info={'label': u'เลขที่หนังสือ'})
    approved_date = db.Column('approved_date', db.Date(), nullable=True, info={'label': u'วันที่อนุมัติ'})
    created_at = db.Column('created_at',db.DateTime(timezone=True),default=datetime.now())
    start_datetime = db.Column('start_datetime', db.DateTime(), nullable=False, info={'label': u'เริ่มต้นการอนุมัติ'})
    end_datetime = db.Column('end_datetime', db.DateTime(), info={'label': u'สิ้นสุดการอนุมัติ'})
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
    org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('document_approval'))
    upload_file_url = db.Column('upload_file_url', db.String())
    file_name = db.Column('file_name', db.String())
    created_staff_id = db.Column('created_staff_id', db.ForeignKey('staff_account.id'))
    created_staff = db.relationship(StaffAccount, backref=db.backref('ot_approval'))
    announce = db.relationship('OtPaymentAnnounce',
                               secondary=ot_announce_document_assoc_table,
                               backref=db.backref('document_approval', lazy='dynamic'))
    staff = db.relationship('StaffAccount',
                            secondary=ot_staff_assoc_table,
                            backref=db.backref('document_approval_staff', lazy='dynamic'))
#    cost_center_id = db.Column('cost_center_id', db.ForeignKey('cost_centers.id'))
#    io_code = db.Column('io_code', db.ForeignKey('iocodes.id'))


class OtRecord(db.Model):
    __tablename__ = 'ot_record'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('ot_record_staff'), foreign_keys=[staff_account_id])
    start_datetime = db.Column('start_datetime', db.DateTime())
    end_datetime = db.Column('end_datetime', db.DateTime())
    compensation_id = db.Column('compensation_id', db.ForeignKey('ot_compensation_rate.id'))
    compensation = db.relationship(OtCompensationRate, backref=db.backref('ot_record_compensation'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=datetime.now())
    created_account_id = db.Column('created_account_id', db.ForeignKey('staff_account.id'))
    created_staff = db.relationship(StaffAccount, backref=db.backref('ot_record_created_staff'),
                                    foreign_keys=[created_account_id])
    org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
    org = db.relationship(Org, backref=db.backref('ot_record'))
    sub_role = db.Column('sub_role', db.String())


