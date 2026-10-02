from app.main import db


class MaintenanceEquipmentType(db.Model):
    __tablename__ = 'maintenance_equipment_types'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def __str__(self):
        return self.name


class MaintenanceRoomEquipment(db.Model):
    __tablename__ = 'maintenance_room_equipment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey('scheduler_room_resources.id'),
        nullable=False,
        index=True
    )
    equipment_type_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_equipment_types.id'),
        nullable=False,
        index=True
    )
    equipment_name = db.Column(db.String(255), nullable=False)
    serial_number = db.Column(db.String(100))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    room = db.relationship(
        'RoomResource',
        backref=db.backref('maintenance_equipment', lazy='dynamic')
    )
    equipment_type = db.relationship(
        'MaintenanceEquipmentType',
        backref=db.backref('room_equipment', lazy='dynamic')
    )


class MaintenanceInspectionSubmission(db.Model):
    __tablename__ = 'maintenance_inspection_submissions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey('scheduler_room_resources.id'),
        nullable=False,
        index=True
    )
    submitted_by_id = db.Column(
        db.Integer,
        db.ForeignKey('staff_account.id'),
        nullable=False,
        index=True
    )
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    room = db.relationship(
        'RoomResource',
        backref=db.backref('maintenance_inspection_submissions', lazy='dynamic')
    )
    submitted_by = db.relationship(
        'StaffAccount',
        foreign_keys=[submitted_by_id],
        backref=db.backref('maintenance_inspection_submissions', lazy='dynamic')
    )


class MaintenanceInspectionItem(db.Model):
    __tablename__ = 'maintenance_inspection_items'
    __table_args__ = (
        db.CheckConstraint(
            "(procurement_detail_id IS NOT NULL AND room_equipment_id IS NULL) OR "
            "(procurement_detail_id IS NULL AND room_equipment_id IS NOT NULL)",
            name='ck_maintenance_inspection_item_equipment_source'
        ),
        db.CheckConstraint(
            "result IN ('normal', 'issue')",
            name='ck_maintenance_inspection_item_result'
        ),
        db.CheckConstraint(
            "result <> 'issue' OR (remark IS NOT NULL AND btrim(remark) <> '')",
            name='ck_maintenance_inspection_item_issue_remark'
        )
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_inspection_submissions.id'),
        nullable=False,
        index=True
    )
    procurement_detail_id = db.Column(
        db.Integer,
        db.ForeignKey('procurement_details.id'),
        index=True
    )
    room_equipment_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_equipment.id'),
        index=True
    )
    inspector_id = db.Column(
        db.Integer,
        db.ForeignKey('staff_account.id'),
        nullable=False,
        index=True
    )
    result = db.Column(db.String(16), nullable=False)
    remark = db.Column(db.Text)
    checked_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    equipment_name_snapshot = db.Column(db.String(255), nullable=False)
    equipment_type_snapshot = db.Column(db.String(100), nullable=False)
    erp_code_snapshot = db.Column(db.String(32))
    serial_number_snapshot = db.Column(db.String(100))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    submission = db.relationship(
        'MaintenanceInspectionSubmission',
        backref=db.backref('items', lazy='dynamic', cascade='all, delete-orphan')
    )
    procurement_detail = db.relationship(
        'ProcurementDetail',
        backref=db.backref('maintenance_inspection_items', lazy='dynamic')
    )
    room_equipment = db.relationship(
        'MaintenanceRoomEquipment',
        backref=db.backref('inspection_items', lazy='dynamic')
    )
    inspector = db.relationship(
        'StaffAccount',
        foreign_keys=[inspector_id],
        backref=db.backref('maintenance_inspection_items', lazy='dynamic')
    )


class MaintenanceRoomSystem(db.Model):
    __tablename__ = 'maintenance_room_systems'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def __str__(self):
        return self.name


class MaintenanceRoomSystemCheckGroup(db.Model):
    __tablename__ = 'maintenance_room_system_check_groups'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    system_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_systems.id'),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(150), nullable=False)
    can_bind_equipment = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    system = db.relationship(
        'MaintenanceRoomSystem',
        backref=db.backref('check_groups', lazy='dynamic', cascade='all, delete-orphan')
    )


class MaintenanceRoomSystemCheckItem(db.Model):
    __tablename__ = 'maintenance_room_system_check_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    check_group_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_system_check_groups.id'),
        nullable=False,
        index=True
    )
    label = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_required = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    check_group = db.relationship(
        'MaintenanceRoomSystemCheckGroup',
        backref=db.backref('check_items', lazy='dynamic', cascade='all, delete-orphan')
    )


class MaintenanceRoomSystemEquipment(db.Model):
    __tablename__ = 'maintenance_room_system_equipment'
    __table_args__ = (
        db.CheckConstraint(
            "(procurement_detail_id IS NOT NULL AND room_equipment_id IS NULL) OR "
            "(procurement_detail_id IS NULL AND room_equipment_id IS NOT NULL)",
            name='ck_maintenance_room_system_equipment_source'
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey('scheduler_room_resources.id'),
        nullable=False,
        index=True
    )
    system_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_systems.id'),
        nullable=False,
        index=True
    )
    check_group_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_system_check_groups.id'),
        nullable=False,
        index=True
    )
    procurement_detail_id = db.Column(
        db.Integer,
        db.ForeignKey('procurement_details.id'),
        index=True
    )
    room_equipment_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_equipment.id'),
        index=True
    )
    display_name_override = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    room = db.relationship(
        'RoomResource',
        backref=db.backref('maintenance_room_system_equipment', lazy='dynamic')
    )
    system = db.relationship(
        'MaintenanceRoomSystem',
        backref=db.backref('room_equipment', lazy='dynamic')
    )
    check_group = db.relationship(
        'MaintenanceRoomSystemCheckGroup',
        backref=db.backref('room_equipment', lazy='dynamic')
    )
    procurement_detail = db.relationship(
        'ProcurementDetail',
        backref=db.backref('maintenance_room_system_equipment', lazy='dynamic')
    )
    room_equipment = db.relationship(
        'MaintenanceRoomEquipment',
        backref=db.backref('room_system_links', lazy='dynamic')
    )


class MaintenanceRoomSystemCheckSubmission(db.Model):
    __tablename__ = 'maintenance_room_system_check_submissions'
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('normal', 'minor_issue', 'unavailable')",
            name='ck_maintenance_room_system_check_submission_status'
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey('scheduler_room_resources.id'),
        nullable=False,
        index=True
    )
    system_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_systems.id'),
        nullable=False,
        index=True
    )
    inspected_by_id = db.Column(
        db.Integer,
        db.ForeignKey('staff_account.id'),
        nullable=False,
        index=True
    )
    checked_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    status = db.Column(db.String(20), nullable=False, default='minor_issue')
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    room = db.relationship(
        'RoomResource',
        backref=db.backref('maintenance_room_system_check_submissions', lazy='dynamic')
    )
    system = db.relationship(
        'MaintenanceRoomSystem',
        backref=db.backref('check_submissions', lazy='dynamic')
    )
    inspected_by = db.relationship(
        'StaffAccount',
        foreign_keys=[inspected_by_id],
        backref=db.backref('maintenance_room_system_check_submissions', lazy='dynamic')
    )


class MaintenanceRoomSystemCheckResult(db.Model):
    __tablename__ = 'maintenance_room_system_check_results'
    __table_args__ = (
        db.UniqueConstraint(
            'submission_id',
            'check_item_id',
            name='uq_maintenance_room_system_check_result_item'
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_system_check_submissions.id'),
        nullable=False,
        index=True
    )
    check_item_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_system_check_items.id'),
        nullable=False,
        index=True
    )
    is_checked = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    submission = db.relationship(
        'MaintenanceRoomSystemCheckSubmission',
        backref=db.backref('check_results', lazy='dynamic', cascade='all, delete-orphan')
    )
    check_item = db.relationship(
        'MaintenanceRoomSystemCheckItem',
        backref=db.backref('check_results', lazy='dynamic')
    )


class MaintenanceRoomSystemCheckSubmissionEquipment(db.Model):
    __tablename__ = 'maintenance_room_system_check_submission_equipment'
    __table_args__ = (
        db.Index('ix_mrscse_submission_id', 'submission_id'),
        db.Index('ix_mrscse_check_group_id', 'check_group_id'),
        db.Index('ix_mrscse_procurement_detail_id', 'procurement_detail_id'),
        db.Index('ix_mrscse_erp_code_snapshot', 'erp_code_snapshot'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_system_check_submissions.id'),
        nullable=False
    )
    check_group_id = db.Column(
        db.Integer,
        db.ForeignKey('maintenance_room_system_check_groups.id'),
        nullable=False
    )
    procurement_detail_id = db.Column(
        db.Integer,
        db.ForeignKey('procurement_details.id')
    )
    erp_code_snapshot = db.Column(db.String(32))
    item_name_snapshot = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    submission = db.relationship(
        'MaintenanceRoomSystemCheckSubmission',
        backref=db.backref('equipment_snapshots', lazy='dynamic', cascade='all, delete-orphan')
    )
    check_group = db.relationship(
        'MaintenanceRoomSystemCheckGroup',
        backref=db.backref('submission_equipment_snapshots', lazy='dynamic')
    )
    procurement_detail = db.relationship(
        'ProcurementDetail',
        backref=db.backref('room_system_check_equipment_snapshots', lazy='dynamic')
    )
