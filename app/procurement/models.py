# -*- coding:utf-8 -*-
from app.main import db
from app.models import Org
from app.room_scheduler.models import RoomResource
from app.staff.models import StaffAccount


class ProcurementDetail(db.Model):
    __tablename__ = 'procurement_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(255), info={'label': u'ชื่อครุภัณฑ์'})
    procurement_no = db.Column('procurement_no', db.String(), info={'label': u'เลขครุภัณฑ์'})
    registration_no = db.Column('registration_no', db.String(), info={'label': u'เลขคุมทะเบียน'})
    university_no = db.Column('university_no', db.String(), info={'label': u'หมายเลขมหาวิทยาลัย'})
    document_no = db.Column('document_no', db.String(), info={'label': u'เอกสารสั่งซื้อเลขที่'})
    erp_code = db.Column('erp_code', db.String(), info={'label': u'รหัส ERP'})
    serial_no = db.Column('serial_no', db.String(), info={'label': u'Serial Number'})
    purchasing_type = db.Column('purchasing_type', db.String(), info={'label': u'จัดซื้อด้วยเงิน',
                                                    'choices': [(c, c) for c in
                                                                [u'งบประมาณ', u'รายได้คณะ', u'เงินบริจาค', u'อื่นๆ']]})
    bought_by = db.Column('bought_by', db.String(), info={'label': u'วิธีการจัดซื้อ', 'choices': [(c, c) for c in
                                                                                  [u'ตกลงราคา', u'สอบราคา',
                                                                                   u'ประกวดราคา', u'วิธีพิเสษ',
                                                                                   u'รับบริจาค', u'e-Auction',
                                                                                   u'วิธีคัดเลือก', u'อื่นๆ']]})
    budget_year = db.Column('budget_year', db.String(), info={'label': u'ปีงบประมาณ'})
    price = db.Column('price', db.String(), info={'label': u'ราคา'})
    quantity = db.Column('quantity', db.String(), info={'label': u'จำนวน'})
    received_date = db.Column('received_date', db.Date(), info={'label': u'วันที่ได้รับ'})
    available = db.Column('available', db.String(), nullable=False, info={'label': u'ความสามารถการใช้งาน'})
    category_id = db.Column('category_id', db.ForeignKey('procurement_categories.id'))
    category = db.relationship('ProcurementCategory',
                               backref=db.backref('items', lazy='dynamic'))
    guarantee = db.Column('guarantee', db.String(), info={'label': u'ประกัน'})
    model = db.Column('model', db.String(), info={'label': u'รุ่น'})
    maker = db.Column('maker', db.String(), info={'label': u'ยี่ห้อ'})
    size = db.Column('size', db.String(), info={'label': u'ขนาด'})
    desc = db.Column('desc', db.String(), info={'label': u'รายละเอียด'})
    comment = db.Column('comment', db.String(), info={'label': u'หมายเหตุ'})
    responsible_person = db.Column('responsible_person', db.String(), info={'label': u'ผู้ดูแลครุภัณฑ์'})
    org_id = db.Column('org_id', db.ForeignKey('orgs.id'))
    org = db.relationship('Org', backref=db.backref('procurements',
                                                    lazy='dynamic',
                                                    cascade='all, delete-orphan'))

    def __str__(self):
        return u'{}: {}'.format(self.name, self.procurement_no)


class ProcurementCategory(db.Model):
    __tablename__ = 'procurement_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(255), nullable=False)

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
    location_id = db.Column('location_id',
                            db.ForeignKey('scheduler_room_resources.id'))
    item_id = db.Column('item_id', db.ForeignKey('procurement_details.id'))
    item = db.relationship('ProcurementDetail',
                           backref=db.backref('records', lazy='dynamic'))
    location = db.relationship(RoomResource,
                               backref=db.backref('items', lazy='dynamic'))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), nullable=False)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    status_id = db.Column('status_id', db.ForeignKey('procurement_statuses.id'))
    status = db.relationship('ProcurementStatus',
                             backref=db.backref('records', lazy='dynamic'))


class ProcurementMaintanance(db.Model):
    __tablename__ = 'procurement_maintanances'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'),
                         nullable=False)
    staff = db.relationship(StaffAccount)
    service = db.Column('service', db.String(255), info={'label': u'ชื่อเครื่อง/การบริการ'})
    explan = db.Column('explan', db.String(), info={'label': u'คำอธิบาย'})
    notice_date = db.Column('start_date', db.Date(), nullable=False, info={'label': u'วันที่แจ้งซ่อม'})
    repair_date = db.Column('repair_date', db.Date(), info={'label': u'วันที่ซ่อมแซม'})
    detail = db.Column('detail', db.String(), info={'label': u'รายละเอียด'})
    note = db.Column('note', db.String(), info={'label': u'หมายเหตุ'})
    type = db.Column('type', db.String(), info={'label': u'ลักษณะการซ่อม',
                                                                      'choices': [(c, c) for c in
                                                                                  [u'ซ่อมได้เลย', u'ซ่อมได้ต้องรออะไหล่',
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

    def __str__(self):
        return self.service

