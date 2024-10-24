# -*- coding:utf-8 -*-
import os

import boto3
import qrcode
from sqlalchemy import func
from wtforms.validators import DataRequired

from app.main import db
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

class ProcurementDetail(db.Model):
    __tablename__ = 'procurement_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), info={'label': u'ชื่อครุภัณฑ์', 'validators': DataRequired()})
    image = db.Column('image', db.Text(), info={'label': u'รูปภาพ'})
    image_url = db.Column('image_url', db.String(), info={'label': u'ที่อยู่รูปภาพ'})
    qrcode = db.Column('qrcode', db.Text(), info={'label': 'QR Code'})
    procurement_no = db.Column('procurement_no', db.String(12), info={'label': u'เลขครุภัณฑ์'})
    document_no = db.Column('document_no', db.String(), info={'label': u'เอกสารสั่งซื้อเลขที่'})
    erp_code = db.Column('erp_code', db.String(22), unique=True, info={'label': u'Inventory Number/ERP'})
    serial_no = db.Column('serial_no', db.String(), info={'label': u'Serial Number', 'validators': DataRequired()})
    bought_by = db.Column('bought_by', db.String(),
                          info={'label': u'วิธีการจัดซื้อ', 'choices': [('None', 'Select how to purchase..'),
                                                                        (u'ประกาศเชิญชวนทั่วไป(E-Bidding)',
                                                                         u'ประกาศเชิญชวนทั่วไป(E-Bidding)'),
                                                                        (u'วิธีคัดเลือก', u'วิธีคัดเลือก'),
                                                                        (u'วิธีเฉพาะเจาะจง', u'วิธีเฉพาะเจาะจง'),
                                                                        (u'รับบริจาค/รับโอน', u'รับบริจาค/รับโอน'),
                                                                        (u'สำรวจเจอ/แจ้งขึ้นทะเบียน',
                                                                         u'สำรวจเจอ/แจ้งขึ้นทะเบียน')]})
    budget_year = db.Column('budget_year', db.String(), info={'label': u'ปีงบประมาณ'})
    price = db.Column('price', db.String(), info={'label': 'Original value(<=10,000)'})
    received_date = db.Column('received_date', db.Date(), info={'label': u'วันที่ได้รับ', 'validators': DataRequired()})
    available = db.Column('available', db.String(), info={'label': u'สภาพของสินทรัพย์'})
    purchasing_type_id = db.Column('purchasing_type_id', db.ForeignKey('procurement_purchasing_types.id'))
    purchasing_type = db.relationship('ProcurementPurchasingType',
                                      backref=db.backref('types', lazy='dynamic'))
    category_id = db.Column('category_id', db.ForeignKey('procurement_categories.id'))
    category = db.relationship('ProcurementCategory',
                               backref=db.backref('items', lazy='dynamic'))
    guarantee = db.Column('guarantee', db.String(), info={'label': u'บริษัทผู้ขาย/บริจาค'})
    start_guarantee_date = db.Column('start_guarantee_date', db.Date(), info={'label': u'วันที่เริ่มประกัน'})
    end_guarantee_date = db.Column('end_guarantee_date', db.Date(), info={'label': u'วันที่สิ้นสุดประกัน'})
    model = db.Column('model', db.String(), info={'label': u'รุ่น', 'validators': DataRequired()})
    maker = db.Column('maker', db.String(), info={'label': u'ยี่ห้อ', 'validators': DataRequired()})
    size = db.Column('size', db.String(), info={'label': u'ขนาด'})
    comment = db.Column('comment', db.Text(), info={'label': u'หมายเหตุ'})
    org_id = db.Column('org_id', db.ForeignKey('orgs.id'))
    org = db.relationship('Org', backref=db.backref('procurements',
                                                    lazy='dynamic',
                                                    cascade='all, delete-orphan'))
    sub_number = db.Column('sub_number', db.Integer(), info={'label': 'Sub Number'})
    curr_acq_value = db.Column('curr_acq_value', db.String(), info={'label': u'มูลค่าที่ได้มา(>10,000)'})
    cost_center = db.Column('cost_center', db.String(8), info={'label': u'ศูนย์ต้นทุน'})
    is_reserved = db.Column('is_reserved', db.Boolean(), default=False)
    company_support = db.Column('company_support', db.String(), info={'label': u'ติดต่อบริษัท'})
    is_instruments = db.Column('is_instruments', db.Boolean(), default=False)
    is_audio_visual_equipment = db.Column('is_audio_visual_equipment', db.Boolean(), default=False)
    trouble_shooter_id = db.Column('trouble_shooter_id', db.ForeignKey('staff_account.id'))
    trouble_shooter = db.relationship(StaffAccount, foreign_keys=[trouble_shooter_id])

    def __str__(self):
        return u'{}: {}'.format(self.name, self.procurement_no)

    @property
    def to_link(self):
        return self.generate_presigned_url(s3, S3_BUCKET_NAME)

    @property
    def staff_responsible(self):
        record = self.records.order_by('ProcurementRecord.updated_at.desc()').first()
        if record:
            return record.staff_responsible
        else:
            return None

    @property
    def current_record(self):
        return self.records.order_by(ProcurementRecord.id.desc()).first()


    def generate_presigned_url(self):

        if self.image_url:
            try:
                return s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': S3_BUCKET_NAME, 'Key': self.image_url},
                    ExpiresIn=3600
                )
            except Exception as e:
                print(f"Error generating presigned URL: {e}")
                #app.logger.error(f"Error generating presigned URL: {e}")
                return None
        return None


    def to_dict(self):

        presigned_url = self.generate_presigned_url()

        return {
            'id': self.id,
            'image': self.image,
            'image_url': presigned_url if presigned_url else self.image_url,
            'name': self.name,
            'procurement_no': self.procurement_no,
            'erp_code': self.erp_code,
            'budget_year': self.budget_year,
            'received_date': self.received_date,
            'available': self.available,
            'is_audio_visual_equipment': self.is_audio_visual_equipment

        }

    def generate_qrcode(self):
        qr = qrcode.QRCode(version=1, box_size=10)
        qr.add_data(self.procurement_no)
        qr.make(fit=True)
        qr_img = qr.make_image()
        qr_img.save('procurement_qrcode.png')
        import base64
        with open("procurement_qrcode.png", "rb") as img_file:
            self.qrcode = base64.b64encode(img_file.read()).decode()
            db.session.add(self)
            db.session.commit()


class ProcurementPurchasingType(db.Model):
    __tablename__ = 'procurement_purchasing_types'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    purchasing_type = db.Column('purchasing_type', db.String(), info={'label': u'จัดซื้อด้วยเงิน'})
    fund = db.Column('fund', db.Integer(), info={'label': u'แหล่งเงิน'})

    def __str__(self):
        return self.purchasing_type


class ProcurementCategory(db.Model):
    __tablename__ = 'procurement_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(), nullable=False)
    code = db.Column(db.Integer())

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
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    updater_id = db.Column('updater_id', db.ForeignKey('staff_account.id'))
    updater = db.relationship(StaffAccount, foreign_keys=[updater_id])
    status_id = db.Column('status_id', db.ForeignKey('procurement_statuses.id'))
    status = db.relationship('ProcurementStatus',
                             backref=db.backref('records', lazy='dynamic'))
    staff_responsible_id = db.Column('staff_responsible_id', db.ForeignKey('staff_account.id'))
    staff_responsible = db.relationship(StaffAccount, foreign_keys=[staff_responsible_id])


class ProcurementCommitteeApproval(db.Model):
    __tablename__ = 'procurement_committee_approvals'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    record_id = db.Column('record_id', db.ForeignKey('procurement_records.id'))
    record = db.relationship('ProcurementRecord',
                             backref=db.backref('approval', uselist=False))
    approver_id = db.Column('approver_id', db.ForeignKey('staff_account.id'))
    approver = db.relationship('StaffAccount',
                               backref=db.backref('staff_approvers'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True))
    approval_comment = db.Column('approval_comment', db.Text(), info={'label': u'ระบุรายละเอียด'})
    asset_status = db.Column('asset_status', db.String(), info={'label': u'สภาพของสินทรัพย์',
                                                                'choices': [(c, c) for c in
                                                                            [u'ใช้งาน', u'เสื่อมสภาพ/รอจำหน่าย',
                                                                             u'หมดความจำเป็น']]})
    checking_result = db.Column('checking_result', db.String(), nullable=False, info={'label': u'ผลการตรวจสอบ'})


class ProcurementRequire(db.Model):
    __tablename__ = 'procurement_requires'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'), nullable=False)
    staff = db.relationship(StaffAccount)
    detail_id = db.Column('detail_id', db.ForeignKey('procurement_details.id'))
    detail = db.relationship('ProcurementDetail',
                              backref=db.backref('repair_records', lazy='dynamic'))
    desc = db.Column('desc', db.Text(), info={'label': u'รายละเอียดที่ต้องการให้บริการหรือปัญหาต่างๆ'})
    notice_date = db.Column('notice_date', db.Date(), nullable=True, info={'label': u'วันที่แจ้งซ่อม'})
    format_service = db.Column('format_service', db.String(), info={'label': u'รูปแบบการให้บริการ'})

    def to_dict(self):
        return {
            'id': self.id,
            'desc': self.desc,
            'notice_date': self.notice_date,
            'format_service': self.format_service
        }


class ProcurementInfoComputer(db.Model):
    __tablename__ = 'procurement_info_computers'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    mac_address = db.Column('mac_address', db.String(), info={'label': 'MAC Address'})
    computer_name = db.Column('computer_name', db.String(), info={'label': u'ชื่อคอมพิวเตอร์'})
    detail_id = db.Column('detail_id', db.ForeignKey('procurement_details.id'))
    detail = db.relationship('ProcurementDetail',
                               backref=db.backref('computer_info', uselist=False))
    cpu_id = db.Column('cpu_id', db.ForeignKey('procurement_info_cpus.id'))
    cpu = db.relationship('ProcurementInfoCPU',
                          backref=db.backref('cpu_of_computers', lazy='dynamic'))
    ram_id = db.Column('ram_id', db.ForeignKey('procurement_info_rams.id'))
    ram = db.relationship('ProcurementInfoRAM',
                          backref=db.backref('ram_of_computers', lazy='dynamic'))
    windows_version_id = db.Column('windows_version_id', db.ForeignKey('procurement_info_windows_versions.id'))
    windows_version = db.relationship('ProcurementInfoWindowsVersion',
                                      backref=db.backref('windows_ver_of_computers', lazy='dynamic'))
    user_id = db.Column('user_id', db.ForeignKey('staff_account.id'))
    user = db.relationship(StaffAccount, foreign_keys=[user_id])
    harddisk = db.Column('harddisk', db.String(), info={'label': u'HDD',
                                                        'choices': [(c, c) for c in
                                                                    [u'SATA', u'SSD', u'อื่นๆ']]})
    capacity = db.Column('capacity', db.String(), info={'label': 'Capacity'})
    note = db.Column('note', db.Text(), info={'label': 'Note'})

    def to_dict(self):
        return {
            'id': self.id,
            'mac_address': self.mac_address,
            'computer_name': self.computer_name,
            'cpu': self.cpu.cpu,
            'ram': self.ram.ram,
            'windows_version': self.windows_version.windows_version,
            'user': self.user.personal_info.fullname,
            'harddisk': self.harddisk,
            'capacity': self.capacity,
            'note': self.note
        }


class ProcurementInfoCPU(db.Model):
    __tablename__ = 'procurement_info_cpus'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    cpu = db.Column('cpu', db.String(), info={'label': 'CPU'})

    def __str__(self):
        return u'{}'.format(self.cpu)


class ProcurementInfoRAM(db.Model):
    __tablename__ = 'procurement_info_rams'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    ram = db.Column('ram', db.String(), info={'label': 'RAM(GB)'})

    def __str__(self):
        return u'{}'.format(self.ram)


class ProcurementInfoWindowsVersion(db.Model):
    __tablename__ = 'procurement_info_windows_versions'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    windows_version = db.Column('windows_version', db.String(), info={'label': 'Windows Version'})

    def __str__(self):
        return u'{}'.format(self.windows_version)


class ProcurementSurveyComputer(db.Model):
    __tablename__ = 'procurement_survey_computers'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    surveyor_id = db.Column('surveyor_id', db.ForeignKey('staff_account.id'))
    surveyor = db.relationship(StaffAccount, foreign_keys=[surveyor_id])
    satisfaction_with_speed_of_use = db.Column('satisfaction_with_speed_of_use', db.String(),
                                               info={'label': u'ความพึงพอใจในสภาพความพร้อมใช้ของเครื่องคอมพิวเตอร์[ความเร็วในการใช้งาน]'})
    satisfaction_with_continuous_work = db.Column('satisfaction_with_continuous_work', db.String(),
                                                  info={'label': u'ความพึงพอใจในสภาพความพร้อมใช้ของเครื่องคอมพิวเตอร์[การทำงานต่อเนื่อง, ไม่ล่ม หรือค้าง]'})
    satisfaction_with_enough_space = db.Column('satisfaction_with_enough_space', db.String(),
                                               info={'label': u'ความพึงพอใจในสภาพความพร้อมใช้ของเครื่องคอมพิวเตอร์[พื้นที่พอเพียง]'})
    personal_info = db.Column('personal_info', db.Boolean(), default=False,
                              info={'label': u'มีการจัดเก็บและประมวลผลข้อมูลส่วนบุคคลในเครื่องคอมพิวเตอร์'})
    check_back_up_file = db.Column('check_back_up_file', db.String(),
                                   info={'label': u'ตรวจสอบการใช้งานแฟ้มข้อมูลสำหรับสำรองข้อมูลใน NAS Server',
                                         'choices': [('None', u'--เลือกรายละเอียดการใช้งาน--'),
                                                     (u'ไม่มีการใช้งาน', u'ไม่มีการใช้งาน'),
                                                     (u'ไม่พบ', u'ไม่พบ'),
                                                     (u'มีการใช้งานเล็กน้อย', u'มีการใช้งานเล็กน้อย'),
                                                     (u'มีการใช้งานอยู่ปกติ', u'มีการใช้งานอยู่ปกติ'),
                                                     (u'มีการใช้งานอยู่ประจำ', u'มีการใช้งานอยู่ประจำ'),
                                                     (u'มีการใช้งานเยอะมาก', u'มีการใช้งานเยอะมาก')]})
    reason_no_backup_file = db.Column('reason_no_backup_file', db.String(),
                                      info={'label': u'สาเหตุที่ไม่มีการใช้งานแฟ้มข้อมูลสำหรับการสำรองข้อมูลไปยัง NAS Server',
                                         'choices': [('None', u'--เลือกรายละเอียดการใช้งาน--'),
                                                     (u'ไม่ทราบ', u'ไม่ทราบ'),
                                                     (u'ไม่สะดวก', u'ไม่สะดวก'),
                                                     (u'ใช้งานไม่เป็น', u'ใช้งานไม่เป็น'),
                                                     (u'อื่นๆ', u'อื่นๆ')]})
    check_anti_virus_update = db.Column('check_anti_virus_update', db.String(),
                                        info={'label': u'ตรวจสอบ Anti-Virus Update',
                                              'choices': [('None', u'--เลือกรายละเอียดการติดตั้ง--'),
                                                          (u'ไม่มีการติดตั้งระบบ', u'ไม่มีการติดตั้งระบบ'),
                                                          (u'มีการติดตั้งและอัพเดตระบบล่าสุด',
                                                           u'มีการติดตั้งและอัพเดตระบบล่าสุด'),
                                                          (u'มีการติดตั้งแต่ไม่ได้อัพเดตระบบล่าสุด',
                                                           u'มีการติดตั้งแต่ไม่ได้อัพเดตระบบล่าสุด')
                                                          ]})
    check_windows_update = db.Column('check_windows_update', db.String(),
                                     info={'label': u'ตรวจสอบ Windows Update',
                                           'choices': [('None', u'--เลือกการอัพเดต--'),
                                                       (u'ไม่มีการอัพเดตเป็นรุ่นล่าสุด', u'ไม่มีการอัพเดตเป็นรุ่นล่าสุด'),
                                                       (u'มีการอัพเดตเป็นรุ่นล่าสุด', u'มีการอัพเดตเป็นรุ่นล่าสุด')
                                                       ]})
    list_software = db.Column('list_software', db.String(),
                              info={'label': u'รายชื่อ Software ที่มีลิขสิทธิ์ไม่ถูกต้อง'})
    setting_user_login = db.Column('setting_user_login', db.String(),
                                   info={'label': u'จัดการตั้งค่ารหัสผ่านสำหรับ User login',
                                         'choices': [('None', u'--เลือกการจัดการ--'),
                                                     (u'จัดการเรียบร้อยแล้ว', u'จัดการเรียบร้อยแล้ว'),
                                                     (u'ยังไม่เรียบร้อย', u'ยังไม่เรียบร้อย')
                                                     ]})
    setting_screen_saver = db.Column('setting_screen_saver', db.String(),
                                     info={'label': u'จัดการตั้งค่ารหัสผ่านการป้องกัน Screen saver',
                                           'choices': [('None', u'--เลือกการจัดการ--'),
                                                       (u'จัดการเรียบร้อยแล้ว', u'จัดการเรียบร้อยแล้ว'),
                                                       (u'ยังไม่เรียบร้อย', u'ยังไม่เรียบร้อย')
                                                       ]})
    check_ms_office_and_windows_activation = db.Column('check_ms_office_and_windows_activation', db.String(),
                                                       info={'label': u'ตรวจสอบ MS-Office and Windows activation',
                                                             'choices': [('None', u'--เลือกการจัดการ--'),
                                                                         (u'จัดการเรียบร้อยแล้ว',
                                                                          u'จัดการเรียบร้อยแล้ว'),
                                                                         (u'ยังไม่เรียบร้อย', u'ยังไม่เรียบร้อย')
                                                                         ]})
    requirement = db.Column('requirement', db.Text(), info={'label': u'ความต้องการเพิ่มเติมหรือข้อเสนอแนะ'})
    survey_date = db.Column('survey_date', db.DateTime(timezone=True), server_default=func.now())
    computer_info_id = db.Column('computer_info_id', db.ForeignKey('procurement_info_computers.id'))
    computer_info = db.relationship('ProcurementInfoComputer', foreign_keys=[computer_info_id],
                             backref=db.backref('survey_records', lazy='dynamic'))


class ProcurementBorrowDetail(db.Model):
    __tablename__ = 'procurement_borrow_details'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    number = db.Column('number', db.String(), info={'label': u'เลขที่หนังสือ'})
    book_date = db.Column('book_date', db.Date(), info={'label': u'วันที่หนังสือ'})
    borrower_id = db.Column('borrower_id', db.ForeignKey('staff_account.id'))
    borrower = db.relationship(StaffAccount)
    type_of_purpose = db.Column('type_of_purpose', db.String(), info={'label': u'ความประสงค์ของยืมพัสดุ'})
    purpose = db.Column('purpose', db.String(), info={'label': u'เพื่อใช้ในงาน'})
    reason = db.Column('reason', db.String(), nullable=False, info={'label': u'ระบุเหตุผลความจำเป็น'})
    location_of_use = db.Column('location_of_use', db.String(), nullable=False, info={'label': u'สถานที่นำไปใช้งาน'})
    address_number = db.Column('address_number', db.String(), info={'label': u'เลขที่'})
    moo = db.Column('moo', db.String(), info={'label': u'หมู่ที่'})
    road = db.Column('road', db.String(), info={'label': u'ถนน'})
    sub_district = db.Column('sub_district', db.String(), info={'label': u'ตำบล/แขวง'})
    district = db.Column('district', db.String(), info={'label': u'อำเภอ/เขต'})
    province = db.Column('province', db.String(), info={'label': u'จังหวัด'})
    postal_code = db.Column('postal_code', db.Integer(), info={'label': u'รหัสไปรษณีย์'})
    start_date = db.Column('start_date', db.Date(), nullable=False, info={'label': u'วันที่เริ่มยืม'})
    end_date = db.Column('end_date', db.Date(), nullable=False, info={'label': u'วันที่สิ้นสุดยืม'})
    created_date = db.Column('created_date', db.DateTime(timezone=True), server_default=func.now())

    @property
    def borrow_status(self):
        if self.start_date:
            return u'อยู่ระหว่างการยืม'
        elif len(self.end_date) > 7:
            return u'เกินกำหนด'
        else:
            return u'คืนเรียบร้อย'

    def to_dict(self):
        return {
            'id': self.id,
            'number': self.number,
            'book_date': self.book_date,
            'purpose': self.purpose,
            'location_of_use': self.location_of_use
        }


class ProcurementBorrowItem(db.Model):
    __tablename__ = 'procurement_borrow_items'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    borrow_detail_id = db.Column('borrow_detail_id', db.ForeignKey('procurement_borrow_details.id'))
    borrow_detail= db.relationship('ProcurementBorrowDetail', backref=db.backref('items', lazy='dynamic'))
    procurement_detail_id = db.Column('procurement_detail_id', db.ForeignKey('procurement_details.id'))
    procurement_detail = db.relationship('ProcurementDetail', backref=db.backref('borrow_items', lazy='dynamic'))
    item = db.Column('item', db.String(), info={'label': u'รายการ'})
    quantity = db.Column('quantity', db.Integer(), info={'label': u'จำนวน'})
    unit = db.Column('unit', db.String(), info={'label': u'หน่วยนับ'})
    note = db.Column('note', db.Text(), info={'label': u'หมายเหตุ'})

    def __str__(self):
        return u'{}: {}'.format(self.borrow_detail.number, self.borrow_detail.book_date)

    def to_dict(self):
        return {
            'id': self.id,
            'item': self.item,
            'quantity': self.quantity,
            'unit': self.unit,
            'note': self.note
        }
