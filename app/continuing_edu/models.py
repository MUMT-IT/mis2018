from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.staff.models import StaffAccount
from app.main import db




class MemberType(db.Model):
    """Lookup table for member types."""
    __tablename__ = 'member_types'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "นักศึกษา ม.มหิดล"
    name_en = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "mahidol_student"

    # Relationship to Member model
    members = relationship("Member", back_populates="member_type_ref", lazy=True)
    event_registration_fees = relationship("EventRegistrationFee", back_populates="member_type_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<MemberType {self.name_en}>"


class Gender(db.Model):
    """Lookup table for genders."""
    __tablename__ = 'genders'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "ชาย"
    name_en = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "male"

    # Relationship to Member model
    members = relationship("Member", back_populates="gender_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<Gender {self.name_en}>"


class AgeRange(db.Model):
    """Lookup table for age ranges."""
    __tablename__ = 'age_ranges'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "ต่ำกว่า 18 ปี"
    name_en = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "under_18"

    # Relationship to Member model
    members = relationship("Member", back_populates="age_range_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<AgeRange {self.name_en}>"


class RegistrationStatus(db.Model):
    """Lookup table for registration statuses."""
    __tablename__ = 'registration_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "ลงทะเบียนแล้ว"
    name_en = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "registered"
    css_badge = db.Column(db.String(100), nullable=True, comment="CSS class for badge styling")  # New field

    # Relationship to MemberRegistration model
    member_registrations = relationship("MemberRegistration", back_populates="status_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<RegistrationStatus {self.name_en}>"


class RegisterPaymentStatus(db.Model):
    """Lookup table for payment statuses."""
    __tablename__ = 'register_payment_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "รอดำเนินการ"
    name_en = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "pending"
    css_badge = db.Column(db.String(100), nullable=True, comment="CSS class for badge styling")  # New field

    # Relationship to RegisterPayment model
    register_payments = relationship("RegisterPayment", back_populates="payment_status_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<RegisterPaymentStatus {self.name_en}>"


class CertificateType(db.Model):
    """Lookup table for certificate types."""
    __tablename__ = 'certificate_types'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "เข้าร่วม"
    name_en = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "participation"

    # Relationship to EventEntity model
    event_entities = relationship("EventEntity", back_populates="certificate_type_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<CertificateType {self.name_en}>"


class MemberCertificateStatus(db.Model):
    """Lookup table for member certificate statuses."""
    __tablename__ = 'member_certificate_statuses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "ออกแล้ว"
    name_en = db.Column(db.String(50), unique=True, nullable=False)  # e.g., "issued"
    css_badge = db.Column(db.String(100), nullable=True, comment="CSS class for badge styling")  # New field

    # Relationship to MemberRegistration model
    member_registrations = relationship("MemberRegistration", back_populates="certificate_status_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<MemberCertificateStatus {self.name_en}>"


# --------------------------------------------------
# Core Models
# --------------------------------------------------
class EntityCategory(db.Model):
    """Defines categories for various entities (e.g., courses, webinars)."""
    __tablename__ = 'entity_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name_th = db.Column(db.String(), nullable=False)
    name_en = db.Column(db.String(), nullable=False)
    description = db.Column(db.String(), nullable=False)

    # Relationship to EventEntity (one-to-many)
    events = relationship("EventEntity", back_populates="category", lazy=True)

    def __str__(self):
        return self.name_en


class Member(db.Model):
    """System user / learner profile"""

    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Changed from String to Integer FK
    member_type_id = db.Column(db.Integer, ForeignKey('member_types.id'), nullable=True)
    member_type_ref = relationship("MemberType", back_populates="members")

    gender_id = db.Column(db.Integer, ForeignKey('genders.id'), nullable=True)
    gender_ref = relationship("Gender", back_populates="members")

    age_range_id = db.Column(db.Integer, ForeignKey('age_ranges.id'), nullable=True)
    age_range_ref = relationship("AgeRange", back_populates="members")

    country = db.Column(db.String(100))
    title_name_th = db.Column(db.String(100))
    title_name_en = db.Column(db.String(100))
    full_name_th = db.Column(db.String(255))
    full_name_en = db.Column(db.String(255))

    address = db.Column(db.String(400))
    province = db.Column(db.String(255))
    zip_code = db.Column(db.String(100))
    phone_no = db.Column(db.String(100))

    policy_accepted = db.Column(db.Boolean)
    terms_condition_accepted = db.Column(db.Boolean)
    received_news = db.Column(db.Boolean)


    is_verified = db.Column(db.Boolean, default=False, nullable=False, comment="ยืนยันอีเมลแล้ว")
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    # New field for total continuing education score
    total_continue_education_score = db.Column(db.Numeric(precision=10, scale=2), default=0.00, nullable=False,
                                               comment="คะแนนการศึกษาต่อเนื่องรวมของสมาชิก")

    # Relationships
    registrations = relationship("MemberRegistration", back_populates="member", lazy=True)
    payments = relationship("RegisterPayment", back_populates="member", lazy=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Member {self.username}>"



# Redesigned EventEntity: merged Course and Webinar fields into one table
class EventEntity(db.Model):
    """
    Represents an academic event (Course, Webinar, etc.) in a single table.
    """
    __tablename__ = 'event_entities'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(50), nullable=False)  # e.g., 'course', 'webinar', etc.

    # Common fields
    title_en = db.Column(db.String(255), nullable=False)
    title_th = db.Column(db.String(255), nullable=True)
    description_en = db.Column(db.Text)
    description_th = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    # Staff/institution
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('events_managed', lazy=True))
    category_id = db.Column(db.Integer, ForeignKey('entity_categories.id'), nullable=True)
    category = relationship("EntityCategory", back_populates="events")
    certificate_type_id = db.Column(db.Integer, ForeignKey('certificate_types.id'), nullable=True)
    certificate_type_ref = relationship("CertificateType", back_populates="event_entities")
    creating_institution = db.Column(db.String(255), nullable=False, default="เทคนิคการแพทย์ ม.มหิดล", comment="สถาบันที่สร้างกิจกรรมนี้")
    department_or_unit = db.Column(db.String(255), nullable=True, comment="ภาควิชา หรือหน่วยงานที่รับผิดชอบกิจกรรม")
    continue_education_score = db.Column(db.Numeric(precision=10, scale=2), default=0.00, nullable=False, comment="คะแนนการศึกษาต่อเนื่อง (ทศนิยม 2 ตำแหน่ง)")

    # Fields from Course
    course_code = db.Column(db.String(100), unique=True, nullable=True)  # nullable for non-course events
    image_url = db.Column(db.Text, nullable=True)
    long_description_en = db.Column(db.Text, nullable=True)
    long_description_th = db.Column(db.Text, nullable=True)
    duration_en = db.Column(db.String(50), nullable=True)
    duration_th = db.Column(db.String(50), nullable=True)
    format_en = db.Column(db.String(100), nullable=True)
    format_th = db.Column(db.String(100), nullable=True)
    certification_en = db.Column(db.String(50), nullable=True)
    certification_th = db.Column(db.String(50), nullable=True)
    location_en = db.Column(db.String(255), nullable=True)
    location_th = db.Column(db.String(255), nullable=True)
    degree_en = db.Column(db.String(50), nullable=True)
    degree_th = db.Column(db.String(50), nullable=True)
    department_owner = db.Column(db.String(50), nullable=True)
    created_by = db.Column(db.String(50), nullable=True)
    certificate_name_th = db.Column(db.String(255), nullable=True, comment="ชื่อใบรับรองภาษาไทย")
    certificate_name_en = db.Column(db.String(255), nullable=True, comment="English certificate name")

    # Relationships
    payments = relationship("RegisterPayment", back_populates="event_entity", lazy=True)
    registrations = relationship("MemberRegistration", back_populates="event_entity", lazy=True)
    speakers = relationship("EventSpeaker", back_populates="event_entity", lazy=True)
    agendas = relationship("EventAgenda", back_populates="event_entity", lazy=True)
    materials = relationship("EventMaterial", back_populates="event_entity", lazy=True)
    registration_fees = relationship("EventRegistrationFee", back_populates="event_entity", lazy=True)
    editors = relationship("EventEditor", back_populates="event_entity", lazy=True)
    registration_reviewers = relationship("EventRegistrationReviewer", back_populates="event_entity", lazy=True)
    payment_approvers = relationship("EventPaymentApprover", back_populates="event_entity", lazy=True)
    receipt_issuers = relationship("EventReceiptIssuer", back_populates="event_entity", lazy=True)
    certificate_managers = relationship("EventCertificateManager", back_populates="event_entity", lazy=True)

    def __repr__(self) -> str:
        return f"<EventEntity {self.event_type}: {self.title_en}>"








# --------------------------------------------------
# Association Tables (now a single generic registration table)
# --------------------------------------------------
class MemberRegistration(db.Model):
    """
    Links members to any EventEntity they have registered for.
    Replaces CourseRegistration and WebinarRegistration.
    """
    __tablename__ = "member_registrations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    member_id = db.Column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_entity_id = db.Column(
        db.Integer, ForeignKey("event_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )

    registration_date = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    # Changed from String to Integer FK
    status_id = db.Column(db.Integer, ForeignKey('registration_statuses.id'), nullable=False,
                          default=1)  # Assuming 'registered' is ID 1
    status_ref = relationship("RegistrationStatus", back_populates="member_registrations")

    # New fields for attendance tracking
    attendance_count = db.Column(db.Integer, default=0, nullable=False,
                                 comment="Number of sessions/times attended")
    total_hours_attended = db.Column(db.Float, default=0.0, nullable=False,
                                     comment="Total hours of attendance")

    # New fields for test tracking
    pre_test_score = db.Column(db.Float, nullable=True, comment="Score from pre-assessment/test")
    post_test_score = db.Column(db.Float, nullable=True, comment="Score from post-assessment/test")
    assessment_passed = db.Column(db.Boolean, nullable=True,
                                  comment="True if assessment criteria met, False otherwise")

    # New fields for certificate tracking
    # Changed from String to Integer FK
    certificate_status_id = db.Column(db.Integer, ForeignKey('member_certificate_statuses.id'), nullable=False,
                                      default=1)  # Assuming 'not_applicable' is ID 1
    certificate_status_ref = relationship("MemberCertificateStatus", back_populates="member_registrations")

    certificate_issued_date = db.Column(db.DateTime(timezone=True), nullable=True,
                                        comment="Date when the certificate was issued")
    certificate_url = db.Column(db.String(500), nullable=True,
                                comment="URL to the issued certificate file")

    __table_args__ = (
        UniqueConstraint("member_id", "event_entity_id", name="_member_event_entity_uc"),
    )

    member = relationship("Member", back_populates="registrations")
    event_entity = relationship("EventEntity", back_populates="registrations")

    def __repr__(self) -> str:  # pragma: no cover
        return (f"<MemberRegistration Member:{self.member_id} Event:{self.event_entity_id} "
                f"Status:{self.status_ref.name_en if self.status_ref else 'N/A'} CertStatus:{self.certificate_status_ref.name_en if self.certificate_status_ref else 'N/A'}>")


class RegisterPaymentReceipt(db.Model):
    """
    Stores details of issued receipts for payments.
    """
    __tablename__ = 'register_payment_receipts'  # Updated table name
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    register_payment_id = db.Column(db.Integer, ForeignKey('register_payments.id', ondelete='CASCADE'), unique=True,
                                    nullable=False)
    receipt_number = db.Column(db.String(100), unique=True, nullable=False, comment="หมายเลขใบเสร็จรับเงิน")
    issue_date = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False,
                           comment="วันที่ออกใบเสร็จ")
    receipt_url = db.Column(db.String(500), nullable=True, comment="URL ของไฟล์ใบเสร็จรับเงิน")
    issued_by_staff_id = db.Column(db.Integer, ForeignKey('staff_account.id'), nullable=True,
                                   comment="Staff ผู้ออกใบเสร็จ")

    # Relationships
    payment = relationship("RegisterPayment", back_populates="receipt")
    issued_by_staff = relationship(StaffAccount, backref=db.backref('receipts_issued', lazy=True))

    def __repr__(self) -> str:
        return f"<RegisterPaymentReceipt No:{self.receipt_number} Payment:{self.register_payment_id}>"  # Updated repr


class RegisterPayment(db.Model):
    """Tracks payment information for event registrations."""
    __tablename__ = "register_payments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    member_id = db.Column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Link to the generic EventEntity, allowing payments for both courses and webinars
    event_entity_id = db.Column(
        db.Integer, ForeignKey("event_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )

    payment_amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    # Changed from String to Integer FK
    payment_status_id = db.Column(db.Integer, ForeignKey('register_payment_statuses.id'), nullable=False,
                                  default=1)  # Assuming 'pending' is ID 1
    payment_status_ref = relationship("RegisterPaymentStatus", back_populates="register_payments")

    transaction_id = db.Column(db.String(255), unique=True, nullable=True,
                               comment="Reference ID from payment gateway")

    # New field for payment proof file URL
    payment_proof_url = db.Column(db.String(500), nullable=True, comment="URL ของไฟล์หลักฐานการชำระเงิน")

    # New fields for staff approval
    approved_by_staff_id = db.Column(db.Integer, ForeignKey('staff_account.id'), nullable=True,
                                     comment="Staff ผู้อนุมัติการชำระเงิน")
    approval_date = db.Column(db.DateTime(timezone=True), nullable=True, comment="วันที่อนุมัติการชำระเงิน")

    # Relationships
    member = relationship("Member", back_populates="payments")
    event_entity = relationship("EventEntity", back_populates="payments")
    approved_by_staff = relationship(StaffAccount, backref=db.backref('payments_approved',
                                                                      lazy=True))  # Relationship to StaffAccount for approval
    receipt = relationship("RegisterPaymentReceipt", back_populates="payment",
                           uselist=False)  # One-to-one relationship with RegisterPaymentReceipt

    def __repr__(self) -> str:
        return f"<RegisterPayment Member:{self.member_id} Event:{self.event_entity_id} Status:{self.payment_status_ref.name_en if self.payment_status_ref else 'N/A'}>"


# --------------------------------------------------
# New Models for Event Details
# --------------------------------------------------
class EventSpeaker(db.Model):
    """
    Stores information about speakers or lecturers for an EventEntity.
    """
    __tablename__ = 'event_speakers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    title_en = db.Column(db.String(255), nullable=False)
    title_th = db.Column(db.String(255), nullable=False)
    name_th = db.Column(db.String(255), nullable=False)
    name_en = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(200), nullable=False)
    position_th = db.Column(db.String(255), nullable=True)
    position_en = db.Column(db.String(255), nullable=True)
    institution_th = db.Column(db.String(255), nullable=False)
    institution_en = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(500), nullable=True, comment="URL to the speaker's photo")
    bio_th = db.Column(db.Text, nullable=True)
    bio_en = db.Column(db.Text, nullable=True)

    # Relationship to EventEntity
    event_entity = relationship("EventEntity", back_populates="speakers")

    def __repr__(self) -> str:
        return f"<EventSpeaker {self.name_en} for Event:{self.event_entity_id}>"


class EventAgenda(db.Model):
    """
    Stores agenda items for an EventEntity.
    """
    __tablename__ = 'event_agendas'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)

    title_th = db.Column(db.String(255), nullable=False)
    title_en = db.Column(db.String(255), nullable=False)
    description_th = db.Column(db.Text, nullable=True)
    description_en = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    order = db.Column(db.Integer, nullable=False, comment="Order of the agenda item")

    # Relationship to EventEntity
    event_entity = relationship("EventEntity", back_populates="agendas")

    def __repr__(self) -> str:
        return f"<EventAgenda {self.title_en} for Event:{self.event_entity_id} from {self.start_time.strftime('%H:%M')} to {self.end_time.strftime('%H:%M')}>"


class EventMaterial(db.Model):
    """
    Stores downloadable materials associated with an EventEntity.
    """
    __tablename__ = 'event_materials'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    order = db.Column(db.Integer, nullable=False, comment="Order of the materials item")
    title_th = db.Column(db.String(255), nullable=False)
    title_en = db.Column(db.String(255), nullable=False)
    description_th = db.Column(db.Text, nullable=True)
    description_en = db.Column(db.Text, nullable=True)
    material_url = db.Column(db.String(500), nullable=False, comment="URL to the downloadable material")
    uploaded_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    # Relationship to EventEntity
    event_entity = relationship("EventEntity", back_populates="materials")

    def __repr__(self) -> str:
        return f"<EventMaterial {self.title_en} for Event:{self.event_entity_id}>"


class EventRegistrationFee(db.Model):
    """
    Stores registration fees for an EventEntity, differentiated by MemberTypeEnum.
    """
    __tablename__ = 'event_registration_fees'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    # Changed from String to Integer FK
    member_type_id = db.Column(db.Integer, ForeignKey('member_types.id'), nullable=False)
    member_type_ref = relationship("MemberType", back_populates="event_registration_fees")

    price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    __table_args__ = (
        UniqueConstraint("event_entity_id", "member_type_id", name="_event_member_type_uc"),
    )

    # Relationship to EventEntity
    event_entity = relationship("EventEntity", back_populates="registration_fees")

    def __repr__(self) -> str:
        return f"<EventRegistrationFee Event:{self.event_entity_id} MemberType:{self.member_type_ref.name_en if self.member_type_ref else 'N/A'} Price:{self.price}>"


# --------------------------------------------------
# New Models for Assigned Staff Roles
# --------------------------------------------------
class EventEditor(db.Model):
    """
    Assigns staff members as editors for a specific EventEntity.
    """
    __tablename__ = 'event_editors'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.Integer, ForeignKey('staff_account.id'), nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    __table_args__ = (
        UniqueConstraint("event_entity_id", "staff_id", name="_event_editor_uc"),
    )

    event_entity = relationship("EventEntity", back_populates="editors")
    staff = relationship(StaffAccount, backref=db.backref('events_edited', lazy=True))

    def __repr__(self) -> str:
        return f"<EventEditor Event:{self.event_entity_id} Staff:{self.staff_id}>"


class EventRegistrationReviewer(db.Model):
    """
    Assigns staff members responsible for reviewing registrations for an EventEntity.
    """
    __tablename__ = 'event_registration_reviewers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.Integer, ForeignKey('staff_account.id'), nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    __table_args__ = (
        UniqueConstraint("event_entity_id", "staff_id", name="_event_registration_reviewer_uc"),
    )

    event_entity = relationship("EventEntity", back_populates="registration_reviewers")
    staff = relationship(StaffAccount, backref=db.backref('registrations_reviewed', lazy=True))

    def __repr__(self) -> str:
        return f"<EventRegistrationReviewer Event:{self.event_entity_id} Staff:{self.staff_id}>"


class EventPaymentApprover(db.Model):
    """
    Assigns staff members responsible for approving payments for an EventEntity.
    """
    __tablename__ = 'event_payment_approvers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.Integer, ForeignKey('staff_account.id'), nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    __table_args__ = (
        UniqueConstraint("event_entity_id", "staff_id", name="_event_payment_approver_uc"),
    )

    event_entity = relationship("EventEntity", back_populates="payment_approvers")
    staff = relationship(StaffAccount,
                         backref=db.backref('payments_approved_roles', lazy=True))  # Renamed backref to avoid conflict

    def __repr__(self) -> str:
        return f"<EventPaymentApprover Event:{self.event_entity_id} Staff:{self.staff_id}>"


class EventReceiptIssuer(db.Model):
    """
    Assigns staff members responsible for issuing receipts for an EventEntity.
    """
    __tablename__ = 'event_receipt_issuers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.Integer, ForeignKey('staff_account.id'), nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    __table_args__ = (
        UniqueConstraint("event_entity_id", "staff_id", name="_event_receipt_issuer_uc"),
    )

    event_entity = relationship("EventEntity", back_populates="receipt_issuers")
    staff = relationship(StaffAccount,
                         backref=db.backref('receipts_issued_roles', lazy=True))  # Renamed backref to avoid conflict

    def __repr__(self) -> str:
        return f"<EventReceiptIssuer Event:{self.event_entity_id} Staff:{self.staff_id}>"


class EventCertificateManager(db.Model):
    """
    Assigns staff members responsible for managing certificates for an EventEntity.
    """
    __tablename__ = 'event_certificate_managers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_entity_id = db.Column(db.Integer, ForeignKey('event_entities.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.Integer, ForeignKey('staff_account.id'), nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    __table_args__ = (
        UniqueConstraint("event_entity_id", "staff_id", name="_event_certificate_manager_uc"),
    )

    event_entity = relationship("EventEntity", back_populates="certificate_managers")
    staff = relationship(StaffAccount, backref=db.backref('certificates_managed', lazy=True))

    def __repr__(self) -> str:
        return f"<EventCertificateManager Event:{self.event_entity_id} Staff:{self.staff_id}>"
