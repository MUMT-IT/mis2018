# -*- coding:utf-8 -*-
from app.main import db
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
    department = db.Column('department', db.String(), info={'label': u'ภาควิชา',
                                                                'choices': [(c, c) for c in
                                                                      [u'-', u'Lab กลาง', u'ภาควิชาเคมีคลินิก',
                                                                       u'สถานเวชศาสตร์ชันสูตร',
                                                                       u'ศูนย์เหมืองข้อมูลและชีวการแพทย์สารสนเทศ',
                                                                       u'ศูนย์พัฒนามาตรฐานและประเมินผลิตภัณฑ์',
                                                                       u'ศูนย์วิจัยพัฒนานวัตกรรม',
                                                                       u'ภาควิชาจุลชีววิทยาคลินิก',
                                                                       u'ภาควิชาจุลทรรศนศาสตร์คลินิก',
                                                                       u'สำนักงานคณบดี', u'เทคนิคการแพทย์ชุมชน',
                                                                       u'ภาควิชารังสีเทคนิค',
                                                                       u'ศูนย์เทคนิคการแพทย์และรังสีเทคนิคนานาชาติ']]})
    building = db.Column('building', db.String(), info={'label': u'อาคาร',
                                                            'choices': [(c, c) for c in
                                                                        [u'ยังไม่ระบุอาคาร',
                                                                         u'ตึกคณะเทคนิคการแพทย์ ศิริราช',
                                                                         u'อาคารวิทยาศาตร์และเทคโนโลยีการแพทย์ ศาลายา',
                                                                         u'อาคารห้องเอ็กซเรย์คอมพิวเตอร์ ศาลายา',
                                                                         u'OPD ชั้น 4 รพ.ศิริราช',
                                                                         u'ศูนย์การแพทย์กาญจนาภิเษก']]})
    floor = db.Column('floor', db.String(), info={'label': u'ชั้น'})
    room = db.Column('room', db.String(), info={'label': u'ห้อง'})
    responsible_person = db.Column('responsible_person', db.String(), info={'label': u'ผู้ดูแลครุภัณฑ์'})
    def __str__(self):
        return u'{}: {}'.format(self.list, self.code)


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



