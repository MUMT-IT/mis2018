# -*- coding:utf-8 -*-
from sqlalchemy import func

from app.main import db
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


class ProcurementDetail(db.Model):
    __tablename__ = 'procurement_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False, info={'label': u'ชื่อครุภัณฑ์'})
    image = db.Column('image', db.Text(), info={'label': u'รูปภาพ'})
    qrcode = db.Column('qrcode', db.Text(), info={'label': 'QR Code'})
    procurement_no = db.Column('procurement_no', db.String(), unique=True, nullable=False, info={'label': u'เลขครุภัณฑ์'})
    document_no = db.Column('document_no', db.String(), info={'label': u'เอกสารสั่งซื้อเลขที่'})
    erp_code = db.Column('erp_code', db.String(), info={'label': u'รหัส ERP/Inventory Number'})
    serial_no = db.Column('serial_no', db.String(), info={'label': u'Serial Number'})
    bought_by = db.Column('bought_by', db.String(), info={'label': u'วิธีการจัดซื้อ', 'choices': [(c, c) for c in
                                                                                  [u'ตกลงราคา', u'สอบราคา',
                                                                                   u'ประกวดราคา', u'วิธีพิเสษ',
                                                                                   u'รับบริจาค', u'e-Auction',
                                                                                   u'วิธีคัดเลือก', u'อื่นๆ']]})
    budget_year = db.Column('budget_year', db.String(), nullable=False, info={'label': u'ปีงบประมาณ'})
    price = db.Column('price', db.String(), info={'label': 'Original value'})
    received_date = db.Column('received_date', db.Date(), info={'label': u'วันที่ได้รับ'})
    available = db.Column('available', db.String(), nullable=False, info={'label': u'สภาพของสินทรัพย์'})
    purchasing_type_id = db.Column('purchasing_type_id', db.ForeignKey('procurement_purchasing_types.id'))
    purchasing_type = db.relationship('ProcurementPurchasingType',
                               backref=db.backref('types', lazy='dynamic'))
    category_id = db.Column('category_id', db.ForeignKey('procurement_categories.id'))
    category = db.relationship('ProcurementCategory',
                               backref=db.backref('items', lazy='dynamic'))
    guarantee = db.Column('guarantee', db.String(), info={'label': u'ประกัน'})
    start_guarantee_date = db.Column('start_guarantee_date', db.Date(), info={'label': u'วันที่เริ่มประกัน'})
    end_guarantee_date = db.Column('end_guarantee_date', db.Date(), info={'label': u'วันที่สิ้นสุดประกัน'})
    model = db.Column('model', db.String(), info={'label': u'รุ่น'})
    maker = db.Column('maker', db.String(), info={'label': u'ยี่ห้อ'})
    size = db.Column('size', db.String(), info={'label': u'ขนาด'})
    comment = db.Column('comment', db.Text(), info={'label': u'หมายเหตุ'})
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount, backref=db.backref('staff_responsible'))
    org_id = db.Column('org_id', db.ForeignKey('orgs.id'))
    org = db.relationship('Org', backref=db.backref('procurements',
                                                    lazy='dynamic',
                                                    cascade='all, delete-orphan'))
    sub_number = db.Column('sub_number', db.Integer(), info={'label': 'Sub Number'})
    curr_acq_value = db.Column('curr_acq_value', db.Float(), info={'label': u'มูลค่าที่ได้มา'})
    approver_id = db.Column('approver_id', db.ForeignKey('procurement_committee_approvals.id'))
    approver = db.relationship('ProcurementCommitteeApproval',
                                      backref=db.backref('approved_items', lazy='dynamic'))

    def __str__(self):
        return u'{}: {}'.format(self.name, self.procurement_no)


class ProcurementPurchasingType(db.Model):
    __tablename__ = 'procurement_purchasing_types'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    purchasing_type = db.Column('purchasing_type', db.String(), info={'label': u'จัดซื้อด้วยเงิน',
                                                                      'choices': [(c, c) for c in
                                                                                  [u'เงินงบประมาณแผ่นดิน', u'เงินรายได้ส่วนงาน']]})
    fund = db.Column('fund', db.Integer(), info={'label': u'แหล่งเงิน'})


class ProcurementCategory(db.Model):
    __tablename__ = 'procurement_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(), nullable=False)

    def __str__(self):
        return self.category


class ProcurementStatus(db.Model):
    __tablename__ = 'procurement_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    status = db.Column('status', db.String())

    def __str__(self):
        return self.status


class ProcurementRecord(db.Model):
    __tablename__ = 'procurement_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_id = db.Column('item_id', db.ForeignKey('procurement_details.id'))
    item = db.relationship('ProcurementDetail',
                           backref=db.backref('records', lazy='dynamic'))
    location_id = db.Column('location_id',
                            db.ForeignKey('scheduler_room_resources.id'))
    location = db.relationship(RoomResource,
                               backref=db.backref('items', lazy='dynamic'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount)
    status_id = db.Column('status_id', db.ForeignKey('procurement_statuses.id'))
    status = db.relationship('ProcurementStatus',
                             backref=db.backref('records', lazy='dynamic'))


class ProcurementCommitteeApproval(db.Model):
    __tablename__ = 'procurement_committee_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship('StaffAccount',
                              backref=db.backref('staff_approvers'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    approval_comment = db.Column('approval_comment', db.String())


class ProcurementRequire(db.Model):
    __tablename__ = 'procurement_requires'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount)
    service_id = db.Column('service_id', db.ForeignKey('procurement_details.id'))
    service = db.relationship('ProcurementDetail',
                           backref=db.backref('details', lazy='dynamic'))
    record_id = db.Column('record_id', db.ForeignKey('procurement_records.id'))
    record = db.relationship('ProcurementRecord', backref=db.backref('records'))
    desc = db.Column('desc', db.Text(), info={'label': u'คำอธิบาย'})
    notice_date = db.Column('notice_date', db.Date(), nullable=True, info={'label': u'วันที่แจ้งซ่อม'})


class ProcurementMaintenance(db.Model):
    __tablename__ = 'procurement_maintenances'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    repair_date = db.Column('repair_date', db.Date(), info={'label': u'วันที่ซ่อมแซม'})
    detail = db.Column('detail', db.Text(), info={'label': u'รายละเอียด'})
    note = db.Column('note', db.String(), info={'label': u'หมายเหตุ'})
    type = db.Column('type', db.String(), info={'label': u'ลักษณะการซ่อม',
                                                'choices': [(c, c) for c in
                                                            [u'ซ่อมได้ทันที', u'ซ่อมได้ต้องรออะไหล่',
                                                             u'ซ่อมค่อนข้างยาก', u'ส่งบริษัทซ่อม',
                                                             u'ควรแทงจำหน่าย', u'อื่นๆ']]})
    company_name = db.Column('company_name', db.String(255), info={'label': u'ชื่อบริษัทส่งซ่อม'})
    contact_name = db.Column('contact_name', db.String(255), info={'label': u'ชื่อผู้ติดต่อ'})
    tel = db.Column('tel', db.Integer(), info={'label': u'เบอร์ผู้ติดต่อ'})
    cost = db.Column('cost', db.Integer(), info={'label': u'ราคาซ่อมที่เสนอ'})
    company_des = db.Column('company_des', db.String(), info={'label': u'รายละเอียดการซ่อมจากบริษัท'})
    require = db.Column('require', db.String(), info={'label': u'ความต้องการอะไหล่',
                                                      'choices': [(c, c) for c in
                                                                  [u'ต้องการเบิกอะไหล่', u'ไม่ต้องการเบิกอะไหล่',
                                                                   u'อื่นๆ']]})

