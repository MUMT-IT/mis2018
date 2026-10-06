from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
import arrow

from app.main import db
from app.maintenance.models import (
    MaintenanceRoomSystem,
    MaintenanceRoomSystemCheckGroup,
    MaintenanceRoomSystemCheckItem,
    MaintenanceRoomSystemEquipment,
    MaintenanceRoomSystemCheckResult,
    MaintenanceRoomSystemCheckSubmissionEquipment,
    MaintenanceRoomSystemCheckSubmission
)
from app.procurement.models import ProcurementCategory, ProcurementDetail, ProcurementRecord
from app.room_scheduler.models import RoomResource
from app.maintenance import maintenancebp

ADVERTISING_EQUIPMENT_CATEGORY = 'ครุภัณฑ์โฆษณาและเผยแพร่'


def _get_latest_room_system_check_statuses(room_ids):
    statuses = {room_id: {} for room_id in room_ids}
    if not room_ids:
        return statuses

    submissions = MaintenanceRoomSystemCheckSubmission.query.filter(
        MaintenanceRoomSystemCheckSubmission.room_id.in_(room_ids)
    ).order_by(
        MaintenanceRoomSystemCheckSubmission.checked_at.desc(),
        MaintenanceRoomSystemCheckSubmission.id.desc()
    ).all()
    today = arrow.now('Asia/Bangkok').date()
    for submission in submissions:
        if submission.system_id in statuses[submission.room_id]:
            continue
        checked_at = arrow.get(submission.checked_at, 'Asia/Bangkok').to('Asia/Bangkok')
        days_since = max(0, (today - checked_at.date()).days)
        statuses[submission.room_id][submission.system_id] = {
            'checked_at': checked_at.strftime('%d/%m/%Y'),
            'days_since': days_since,
            'is_overdue': days_since > 30,
            'status': submission.status
        }
    return statuses


@maintenancebp.route('/list-room')
def maintenance_list_room():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    per_page = 10

    query = RoomResource.query.join(
        MaintenanceRoomSystemEquipment,
        MaintenanceRoomSystemEquipment.room_id == RoomResource.id
    ).distinct()
    if q:
        parts = q.split(None, 1)
        if len(parts) == 2:
            number_part, location_part = parts
            query = query.filter(
                RoomResource.number.ilike(f'%{number_part}%'),
                RoomResource.location.ilike(f'%{location_part}%')
            )
        else:
            query = query.filter(or_(
                RoomResource.number.ilike(f'%{q}%'),
                RoomResource.location.ilike(f'%{q}%')
            ))

    pagination = query.order_by(
        RoomResource.number.asc(),
        RoomResource.location.asc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    system_statuses = _get_latest_room_system_check_statuses(
        [room.id for room in pagination.items]
    )
    systems = MaintenanceRoomSystem.query.filter_by(is_active=True).order_by(
        MaintenanceRoomSystem.sort_order.asc(),
        MaintenanceRoomSystem.name.asc()
    ).all()
    return render_template(
        'maintenance/maintenance_list_room.html',
        pagination=pagination,
        q=q,
        systems=systems,
        system_statuses=system_statuses
    )


@maintenancebp.route('/system-check', methods=['GET', 'POST'])
@login_required
def maintenance_system_check():
    room_id = request.args.get('room_id', type=int)
    room = RoomResource.query.get_or_404(room_id)

    linked_system_ids = db.session.query(
        MaintenanceRoomSystemEquipment.system_id
    ).filter(
        MaintenanceRoomSystemEquipment.room_id == room.id,
        MaintenanceRoomSystemEquipment.is_active.is_(True)
    ).distinct().subquery()
    systems = MaintenanceRoomSystem.query.filter(
        MaintenanceRoomSystem.id.in_(linked_system_ids),
        MaintenanceRoomSystem.is_active.is_(True)
    ).order_by(
        MaintenanceRoomSystem.sort_order.asc(),
        MaintenanceRoomSystem.name.asc()
    ).all()
    allowed_system_ids = {system.id for system in systems}

    groups_by_system = {}
    items_by_group = {}
    equipment_by_group = {}
    for system in systems:
        groups = system.check_groups.filter_by(is_active=True).order_by(
            MaintenanceRoomSystemCheckGroup.sort_order.asc(),
            MaintenanceRoomSystemCheckGroup.name.asc()
        ).all()
        groups_by_system[system.id] = groups
        for group in groups:
            items_by_group[group.id] = group.check_items.filter_by(is_active=True).order_by(
                MaintenanceRoomSystemCheckItem.sort_order.asc(),
                MaintenanceRoomSystemCheckItem.label.asc()
            ).all()
            equipment_by_group[group.id] = MaintenanceRoomSystemEquipment.query.filter(
                MaintenanceRoomSystemEquipment.room_id == room.id,
                MaintenanceRoomSystemEquipment.check_group_id == group.id,
                MaintenanceRoomSystemEquipment.is_active.is_(True),
                MaintenanceRoomSystemEquipment.procurement_detail_id.isnot(None)
            ).order_by(MaintenanceRoomSystemEquipment.id.asc()).all()

    if request.method == 'POST':
        checked_item_ids = set(request.form.getlist('checked_item_ids', type=int))
        systems_to_save = []
        errors = []
        for system in systems:
            check_items = [
                item
                for group in groups_by_system[system.id]
                for item in items_by_group[group.id]
            ]
            system_item_ids = {item.id for item in check_items}
            system_checked_item_ids = checked_item_ids.intersection(system_item_ids)
            remark = request.form.get(f'remark-{system.id}', '', type=str).strip() or None
            is_unavailable = system.id in set(request.form.getlist('unavailable_system_ids', type=int))
            if not system_checked_item_ids and not remark and not is_unavailable:
                continue
            if is_unavailable and not remark:
                errors.append(f'{system.name}: กรุณาระบุหมายเหตุเมื่อเลือกไม่พร้อมใช้งาน')
                continue
            missing_required = [
                item.label for item in check_items
                if item.is_required and item.id not in system_checked_item_ids
            ]
            if missing_required and not is_unavailable:
                errors.append(f'{system.name}: กรุณาตรวจรายการบังคับ ' + ', '.join(missing_required))
                continue
            status = (
                'unavailable' if is_unavailable
                else ('normal' if check_items and len(system_checked_item_ids) == len(check_items) else 'minor_issue')
            )
            systems_to_save.append((system, check_items, system_checked_item_ids, remark, status))

        if not systems_to_save and not errors:
            errors.append('กรุณาติ๊ก checklist หรือกรอกหมายเหตุอย่างน้อย 1 ระบบ')
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            checked_at = arrow.now('Asia/Bangkok').datetime
            for system, check_items, system_checked_item_ids, remark, status in systems_to_save:
                submission = MaintenanceRoomSystemCheckSubmission(
                    room_id=room.id,
                    system_id=system.id,
                    inspected_by_id=current_user.id,
                    checked_at=checked_at,
                    status=status,
                    remark=remark
                )
                db.session.add(submission)
                db.session.flush()
                for check_item in check_items:
                    db.session.add(MaintenanceRoomSystemCheckResult(
                        submission_id=submission.id,
                        check_item_id=check_item.id,
                        is_checked=check_item.id in system_checked_item_ids
                    ))
                for group in groups_by_system[system.id]:
                    for equipment_link in equipment_by_group[group.id]:
                        equipment = equipment_link.procurement_detail
                        db.session.add(MaintenanceRoomSystemCheckSubmissionEquipment(
                            submission_id=submission.id,
                            check_group_id=group.id,
                            procurement_detail_id=equipment.id,
                            erp_code_snapshot=equipment.erp_code,
                            item_name_snapshot=equipment.name
                        ))
            db.session.commit()
            flash('บันทึกการตรวจเช็คอุปกรณ์เรียบร้อย', 'success')
            return redirect(url_for('maintenance.maintenance_system_check', room_id=room.id))

    latest_submissions = {}
    submission_rows = MaintenanceRoomSystemCheckSubmission.query.filter(
        MaintenanceRoomSystemCheckSubmission.room_id == room.id,
        MaintenanceRoomSystemCheckSubmission.system_id.in_(allowed_system_ids)
    ).order_by(
        MaintenanceRoomSystemCheckSubmission.checked_at.desc(),
        MaintenanceRoomSystemCheckSubmission.id.desc()
    ).all() if allowed_system_ids else []
    for submission in submission_rows:
        latest_submissions.setdefault(submission.system_id, submission)

    return render_template(
        'maintenance/maintenance_system_check.html',
        room=room,
        systems=systems,
        groups_by_system=groups_by_system,
        items_by_group=items_by_group,
        equipment_by_group=equipment_by_group,
        latest_submissions=latest_submissions
    )


@maintenancebp.route('/system-check-history')
@login_required
def maintenance_system_check_history():
    room_id = request.args.get('room_id', type=int)
    room = RoomResource.query.get_or_404(room_id)
    page = request.args.get('page', 1, type=int)
    pagination = MaintenanceRoomSystemCheckSubmission.query.filter_by(
        room_id=room.id
    ).order_by(
        MaintenanceRoomSystemCheckSubmission.checked_at.desc(),
        MaintenanceRoomSystemCheckSubmission.id.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    return render_template(
        'maintenance/maintenance_system_check_history.html',
        room=room,
        pagination=pagination,
        submissions=pagination.items
    )


@maintenancebp.route('/system-check-history/<int:room_id>/submission/<int:submission_id>')
@login_required
def maintenance_system_check_history_details(room_id, submission_id):
    submission = MaintenanceRoomSystemCheckSubmission.query.filter_by(
        id=submission_id,
        room_id=room_id
    ).first_or_404()
    results = submission.check_results.join(
        MaintenanceRoomSystemCheckItem
    ).order_by(
        MaintenanceRoomSystemCheckItem.sort_order.asc(),
        MaintenanceRoomSystemCheckItem.label.asc()
    ).all()
    equipment_snapshots = submission.equipment_snapshots.join(
        MaintenanceRoomSystemCheckGroup
    ).order_by(
        MaintenanceRoomSystemCheckGroup.sort_order.asc(),
        MaintenanceRoomSystemCheckSubmissionEquipment.id.asc()
    ).all()
    return render_template(
        'maintenance/_maintenance_system_check_history_results.html',
        results=results,
        equipment_snapshots=equipment_snapshots
    )


@maintenancebp.route('/print-qr-room')
def print_qr_room():
    q = request.args.get('q', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    room_ids = request.args.getlist('room_id', type=int)[:2]
    query = RoomResource.query
    if q:
        parts = q.split(None, 1)
        if len(parts) == 2:
            query = query.filter(
                RoomResource.number.ilike(f'%{parts[0]}%'),
                RoomResource.location.ilike(f'%{parts[1]}%')
            )
        else:
            query = query.filter(or_(
                RoomResource.number.ilike(f'%{q}%'),
                RoomResource.location.ilike(f'%{q}%')
            ))
    pagination = query.order_by(RoomResource.number.asc(), RoomResource.location.asc()).paginate(
        page=page,
        per_page=10,
        error_out=False
    )
    selected_rooms_by_id = {
        room.id: room for room in RoomResource.query.filter(RoomResource.id.in_(room_ids)).all()
    } if room_ids else {}
    selected_rooms = [selected_rooms_by_id[room_id] for room_id in room_ids if room_id in selected_rooms_by_id]
    return render_template(
        'maintenance/print_qr_room.html',
        q=q,
        selected_room_ids=[room.id for room in selected_rooms],
        selected_rooms=selected_rooms,
        rooms=pagination.items,
        pagination=pagination
    )


@maintenancebp.route('/scan-room')
def maintenance_scan_room():
    return render_template(
        'maintenance/maintenance_scan_room.html'
    )


@maintenancebp.route('/room-system-setting', methods=['GET', 'POST'])
@login_required
def maintenance_room_system_setting():
    if request.method == 'POST':
        name = request.form.get('name', '', type=str).strip()
        sort_order = request.form.get('sort_order', 0, type=int) or 0

        if not name:
            flash('กรุณากรอกชื่อระบบ', 'danger')
        elif MaintenanceRoomSystem.query.filter_by(name=name).first():
            flash('ชื่อระบบนี้มีอยู่แล้ว', 'danger')
        else:
            db.session.add(MaintenanceRoomSystem(
                name=name,
                sort_order=sort_order,
                is_active='is_active' in request.form
            ))
            db.session.commit()
            flash('เพิ่มระบบหลักเรียบร้อยแล้ว', 'success')
            return redirect(url_for('maintenance.maintenance_room_system_setting'))

    systems = MaintenanceRoomSystem.query.order_by(
        MaintenanceRoomSystem.sort_order.asc(),
        MaintenanceRoomSystem.name.asc()
    ).all()
    groups_by_system = {
        system.id: system.check_groups.order_by(
            MaintenanceRoomSystemCheckGroup.sort_order.asc(),
            MaintenanceRoomSystemCheckGroup.name.asc()
        ).all()
        for system in systems
    }
    items_by_group = {
        group.id: group.check_items.order_by(
            MaintenanceRoomSystemCheckItem.sort_order.asc(),
            MaintenanceRoomSystemCheckItem.label.asc()
        ).all()
        for groups in groups_by_system.values()
        for group in groups
    }
    return render_template(
        'maintenance/maintenance_room_system_setting.html',
        systems=systems,
        groups_by_system=groups_by_system,
        items_by_group=items_by_group
    )


@maintenancebp.route('/room-system-admin')
@login_required
def maintenance_room_system_admin():
    return render_template('maintenance/maintenance_room_system_admin.html')


@maintenancebp.route('/room-system-equipment-admin')
@login_required
def edit_maintenance_room_system_item():
    search_text = request.args.get('q', '', type=str).strip()
    selected_room_id = request.args.get('room_id', type=int)
    selected_category_id = request.args.get('category_id', type=int)
    has_category_filter = 'category_id' in request.args

    room_query = RoomResource.query
    if search_text:
        room_query = room_query.filter(
            or_(
                RoomResource.number.ilike(f'%{search_text}%'),
                RoomResource.location.ilike(f'%{search_text}%'),
                func.concat(RoomResource.number, ' ', RoomResource.location).ilike(
                    f'%{search_text}%'
                )
            )
        )
    rooms = room_query.order_by(RoomResource.number.asc(), RoomResource.location.asc()).limit(20).all()
    room = RoomResource.query.get_or_404(selected_room_id) if selected_room_id else None

    systems = MaintenanceRoomSystem.query.filter_by(is_active=True).order_by(
        MaintenanceRoomSystem.sort_order.asc(),
        MaintenanceRoomSystem.name.asc()
    ).all()
    check_groups = MaintenanceRoomSystemCheckGroup.query.join(
        MaintenanceRoomSystem
    ).filter(
        MaintenanceRoomSystem.is_active.is_(True),
        MaintenanceRoomSystemCheckGroup.is_active.is_(True)
    ).order_by(
        MaintenanceRoomSystem.sort_order.asc(),
        MaintenanceRoomSystemCheckGroup.sort_order.asc(),
        MaintenanceRoomSystemCheckGroup.name.asc()
    ).all()

    procurement_assets = []
    procurement_categories = []
    linked_equipment = []
    if room:
        procurement_categories = ProcurementCategory.query.order_by(
            ProcurementCategory.category.asc()
        ).all()
        if not has_category_filter:
            default_category = ProcurementCategory.query.filter_by(
                category=ADVERTISING_EQUIPMENT_CATEGORY
            ).first()
            selected_category_id = default_category.id if default_category else None
        latest_record_sq = db.session.query(
            ProcurementRecord.item_id,
            func.max(ProcurementRecord.id).label('latest_record_id')
        ).group_by(ProcurementRecord.item_id).subquery()

        if selected_category_id:
            procurement_assets = ProcurementDetail.query.join(
                latest_record_sq,
                ProcurementDetail.id == latest_record_sq.c.item_id
            ).join(
                ProcurementRecord,
                ProcurementRecord.id == latest_record_sq.c.latest_record_id
            ).outerjoin(
                ProcurementCategory,
                ProcurementCategory.id == ProcurementDetail.category_id
            ).filter(
                ProcurementRecord.location_id == room.id,
                ProcurementDetail.category_id == selected_category_id
            ).order_by(ProcurementDetail.name.asc()).all()

        linked_equipment = MaintenanceRoomSystemEquipment.query.join(
            MaintenanceRoomSystem
        ).join(
            MaintenanceRoomSystemCheckGroup
        ).filter(
            MaintenanceRoomSystemEquipment.room_id == room.id
        ).order_by(
            MaintenanceRoomSystem.sort_order.asc(),
            MaintenanceRoomSystemCheckGroup.sort_order.asc(),
            MaintenanceRoomSystemEquipment.id.asc()
        ).all()

    return render_template(
        'maintenance/edit_maintenance_room_system_item.html',
        search_text=search_text,
        rooms=rooms,
        room=room,
        systems=systems,
        check_groups=check_groups,
        procurement_assets=procurement_assets,
        procurement_categories=procurement_categories,
        selected_category_id=selected_category_id,
        linked_equipment=linked_equipment
    )


@maintenancebp.route('/room-system-equipment-admin/bind', methods=['POST'])
@login_required
def bind_maintenance_room_system_equipment():
    room_id = request.form.get('room_id', type=int)
    check_group_id = request.form.get('check_group_id', type=int)
    source_type = request.form.get('source_type', '', type=str)
    source_id = request.form.get('source_id', type=int)

    room = RoomResource.query.get_or_404(room_id)
    check_group = MaintenanceRoomSystemCheckGroup.query.join(
        MaintenanceRoomSystem
    ).filter(
        MaintenanceRoomSystemCheckGroup.id == check_group_id,
        MaintenanceRoomSystemCheckGroup.is_active.is_(True),
        MaintenanceRoomSystem.is_active.is_(True)
    ).first_or_404()

    if source_type == 'procurement':
        latest_record_sq = db.session.query(
            ProcurementRecord.item_id,
            func.max(ProcurementRecord.id).label('latest_record_id')
        ).group_by(ProcurementRecord.item_id).subquery()
        procurement_asset = ProcurementDetail.query.join(
            latest_record_sq,
            ProcurementDetail.id == latest_record_sq.c.item_id
        ).join(
            ProcurementRecord,
            ProcurementRecord.id == latest_record_sq.c.latest_record_id
        ).filter(
            ProcurementDetail.id == source_id,
            ProcurementRecord.location_id == room.id
        ).first_or_404()
        duplicate = MaintenanceRoomSystemEquipment.query.filter_by(
            room_id=room.id,
            procurement_detail_id=procurement_asset.id
        ).first()
        new_link = MaintenanceRoomSystemEquipment(
            room_id=room.id,
            system_id=check_group.system_id,
            check_group_id=check_group.id,
            procurement_detail_id=procurement_asset.id
        )
    else:
        flash('ไม่พบแหล่งข้อมูลครุภัณฑ์ที่ต้องการผูก', 'danger')
        return redirect(url_for('maintenance.edit_maintenance_room_system_item', room_id=room.id))

    if duplicate:
        flash('ครุภัณฑ์รายการนี้ถูกผูกกับระบบตรวจเช็คของห้องนี้แล้ว', 'warning')
    else:
        placeholder = MaintenanceRoomSystemEquipment.query.filter(
            MaintenanceRoomSystemEquipment.room_id == room.id,
            MaintenanceRoomSystemEquipment.check_group_id == check_group.id,
            MaintenanceRoomSystemEquipment.procurement_detail_id.is_(None)
        ).first()
        db.session.add(new_link)
        if placeholder:
            db.session.delete(placeholder)
        db.session.commit()
        flash('บันทึกการผูกครุภัณฑ์เข้ากับระบบตรวจเช็คเรียบร้อยแล้ว', 'success')

    return redirect(url_for('maintenance.edit_maintenance_room_system_item', room_id=room.id))


@maintenancebp.route('/room-system-equipment-admin/bind-system', methods=['POST'])
@login_required
def bind_maintenance_room_system_without_equipment():
    room_id = request.form.get('room_id', type=int)
    check_group_id = request.form.get('check_group_id', type=int)
    room = RoomResource.query.get_or_404(room_id)
    check_group = MaintenanceRoomSystemCheckGroup.query.join(
        MaintenanceRoomSystem
    ).filter(
        MaintenanceRoomSystemCheckGroup.id == check_group_id,
        MaintenanceRoomSystemCheckGroup.is_active.is_(True),
        MaintenanceRoomSystem.is_active.is_(True)
    ).first_or_404()

    duplicate = MaintenanceRoomSystemEquipment.query.filter(
        MaintenanceRoomSystemEquipment.room_id == room.id,
        MaintenanceRoomSystemEquipment.check_group_id == check_group.id,
        MaintenanceRoomSystemEquipment.procurement_detail_id.is_(None)
    ).first()
    if duplicate:
        flash('ระบบหรือกลุ่มตรวจเช็คนี้ถูกเพิ่มให้ห้องนี้แล้ว', 'warning')
    else:
        db.session.add(MaintenanceRoomSystemEquipment(
            room_id=room.id,
            system_id=check_group.system_id,
            check_group_id=check_group.id,
            procurement_detail_id=None
        ))
        db.session.commit()
        flash('เพิ่มระบบตรวจเช็คสำหรับห้องเรียบร้อยแล้ว', 'success')

    return redirect(url_for('maintenance.edit_maintenance_room_system_item', room_id=room.id))


@maintenancebp.route('/room-system-equipment-admin/<int:link_id>/delete', methods=['POST'])
@login_required
def delete_maintenance_room_system_equipment_link(link_id):
    linked_equipment = MaintenanceRoomSystemEquipment.query.get_or_404(link_id)
    room_id = linked_equipment.room_id
    db.session.delete(linked_equipment)
    db.session.commit()
    flash('ยกเลิกการผูกครุภัณฑ์ออกจากระบบตรวจเช็คเรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.edit_maintenance_room_system_item', room_id=room_id))


@maintenancebp.route('/room-system-setting/<int:system_id>/edit', methods=['POST'])
@login_required
def edit_maintenance_room_system(system_id):
    system = MaintenanceRoomSystem.query.get_or_404(system_id)
    name = request.form.get('name', '', type=str).strip()
    sort_order = request.form.get('sort_order', 0, type=int) or 0

    duplicate = MaintenanceRoomSystem.query.filter(
        MaintenanceRoomSystem.id != system.id,
        MaintenanceRoomSystem.name == name
    ).first()
    if not name:
        flash('กรุณากรอกชื่อระบบ', 'danger')
    elif duplicate:
        flash('ชื่อระบบนี้มีอยู่แล้ว', 'danger')
    else:
        system.name = name
        system.sort_order = sort_order
        system.is_active = 'is_active' in request.form
        db.session.commit()
        flash('แก้ไขระบบหลักเรียบร้อยแล้ว', 'success')

    return redirect(url_for('maintenance.maintenance_room_system_setting'))

@maintenancebp.route('/room-system-setting/<int:system_id>/delete', methods=['POST'])
@login_required
def delete_maintenance_room_system(system_id):
    system = MaintenanceRoomSystem.query.get_or_404(system_id)
    if system.check_groups.count() or system.room_equipment.count() or system.check_submissions.count():
        flash('ไม่สามารถลบระบบที่มีกลุ่มอุปกรณ์ ครุภัณฑ์ หรือประวัติการตรวจได้ กรุณาปิดใช้งานแทน', 'danger')
    else:
        db.session.delete(system)
        db.session.commit()
        flash('ลบระบบหลักเรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_room_system_setting'))


@maintenancebp.route('/room-system-setting/<int:system_id>/groups', methods=['POST'])
@login_required
def add_maintenance_room_system_check_group(system_id):
    system = MaintenanceRoomSystem.query.get_or_404(system_id)
    name = request.form.get('name', '', type=str).strip()
    sort_order = request.form.get('sort_order', 0, type=int) or 0

    if not name:
        flash('กรุณากรอกชื่อกลุ่มอุปกรณ์หรือหมวดตรวจเช็ค', 'danger')
    elif system.check_groups.filter_by(name=name).first():
        flash('กลุ่มอุปกรณ์หรือหมวดตรวจเช็คนี้มีอยู่แล้วในระบบนี้', 'danger')
    else:
        db.session.add(MaintenanceRoomSystemCheckGroup(
            system_id=system.id,
            name=name,
            sort_order=sort_order,
            is_active='is_active' in request.form
        ))
        db.session.commit()
        flash('เพิ่มกลุ่มอุปกรณ์หรือหมวดตรวจเช็คเรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_room_system_setting'))


@maintenancebp.route('/room-system-setting/groups/<int:group_id>/edit', methods=['POST'])
@login_required
def edit_maintenance_room_system_check_group(group_id):
    check_group = MaintenanceRoomSystemCheckGroup.query.get_or_404(group_id)
    name = request.form.get('name', '', type=str).strip()
    sort_order = request.form.get('sort_order', 0, type=int) or 0
    duplicate = MaintenanceRoomSystemCheckGroup.query.filter(
        MaintenanceRoomSystemCheckGroup.id != check_group.id,
        MaintenanceRoomSystemCheckGroup.system_id == check_group.system_id,
        MaintenanceRoomSystemCheckGroup.name == name
    ).first()

    if not name:
        flash('กรุณากรอกชื่อกลุ่มอุปกรณ์หรือหมวดตรวจเช็ค', 'danger')
    elif duplicate:
        flash('กลุ่มอุปกรณ์หรือหมวดตรวจเช็คนี้มีอยู่แล้วในระบบนี้', 'danger')
    else:
        check_group.name = name
        check_group.sort_order = sort_order
        check_group.is_active = 'is_active' in request.form
        db.session.commit()
        flash('แก้ไขกลุ่มอุปกรณ์หรือหมวดตรวจเช็คเรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_room_system_setting'))


@maintenancebp.route('/room-system-setting/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_maintenance_room_system_check_group(group_id):
    check_group = MaintenanceRoomSystemCheckGroup.query.get_or_404(group_id)
    if check_group.check_items.count() or check_group.room_equipment.count():
        flash('ไม่สามารถลบกลุ่มที่มี checklist หรือครุภัณฑ์ที่ผูกไว้ได้ กรุณาปิดใช้งานแทน', 'danger')
    else:
        db.session.delete(check_group)
        db.session.commit()
        flash('ลบกลุ่มอุปกรณ์หรือหมวดตรวจเช็คเรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_room_system_setting'))


@maintenancebp.route('/room-system-setting/groups/<int:group_id>/items', methods=['POST'])
@login_required
def add_maintenance_room_system_check_item(group_id):
    check_group = MaintenanceRoomSystemCheckGroup.query.get_or_404(group_id)
    label = request.form.get('label', '', type=str).strip()
    sort_order = request.form.get('sort_order', 0, type=int) or 0

    if not label:
        flash('กรุณากรอกข้อความ checklist', 'danger')
    elif check_group.check_items.filter_by(label=label).first():
        flash('ข้อความ checklist นี้มีอยู่แล้วในกลุ่มนี้', 'danger')
    else:
        db.session.add(MaintenanceRoomSystemCheckItem(
            check_group_id=check_group.id,
            label=label,
            sort_order=sort_order,
            is_required='is_required' in request.form,
            is_active='is_active' in request.form
        ))
        db.session.commit()
        flash('เพิ่มข้อความ checklist เรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_room_system_setting'))


@maintenancebp.route('/room-system-setting/items/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_maintenance_room_system_check_item(item_id):
    check_item = MaintenanceRoomSystemCheckItem.query.get_or_404(item_id)
    label = request.form.get('label', '', type=str).strip()
    sort_order = request.form.get('sort_order', 0, type=int) or 0
    duplicate = MaintenanceRoomSystemCheckItem.query.filter(
        MaintenanceRoomSystemCheckItem.id != check_item.id,
        MaintenanceRoomSystemCheckItem.check_group_id == check_item.check_group_id,
        MaintenanceRoomSystemCheckItem.label == label
    ).first()

    if not label:
        flash('กรุณากรอกข้อความ checklist', 'danger')
    elif duplicate:
        flash('ข้อความ checklist นี้มีอยู่แล้วในกลุ่มนี้', 'danger')
    else:
        check_item.label = label
        check_item.sort_order = sort_order
        check_item.is_required = 'is_required' in request.form
        check_item.is_active = 'is_active' in request.form
        db.session.commit()
        flash('แก้ไขข้อความ checklist เรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_room_system_setting'))


@maintenancebp.route('/room-system-setting/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_maintenance_room_system_check_item(item_id):
    check_item = MaintenanceRoomSystemCheckItem.query.get_or_404(item_id)
    if check_item.check_results.count():
        flash('ไม่สามารถลบ checklist ที่มีผลตรวจแล้ว กรุณาปิดใช้งานแทน', 'danger')
    else:
        db.session.delete(check_item)
        db.session.commit()
        flash('ลบข้อความ checklist เรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_room_system_setting'))
