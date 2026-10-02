from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import String, cast, func, literal, or_
import arrow

from app.main import db
from app.maintenance.models import (
    MaintenanceEquipmentType,
    MaintenanceInspectionItem,
    MaintenanceInspectionSubmission,
    MaintenanceRoomSystem,
    MaintenanceRoomSystemCheckGroup,
    MaintenanceRoomSystemCheckItem,
    MaintenanceRoomSystemEquipment,
    MaintenanceRoomSystemCheckResult,
    MaintenanceRoomSystemCheckSubmissionEquipment,
    MaintenanceRoomSystemCheckSubmission,
    MaintenanceRoomEquipment
)
from app.procurement.models import ProcurementCategory, ProcurementDetail, ProcurementRecord
from app.room_scheduler.models import RoomResource
from app.maintenance import maintenancebp

COMPUTER_EQUIPMENT_CATEGORY = 'ครุภัณฑ์คอมพิวเตอร์'
ADVERTISING_EQUIPMENT_CATEGORY = 'ครุภัณฑ์โฆษณาและเผยแพร่'
MAINTENANCE_PROCUREMENT_CATEGORIES = (
    COMPUTER_EQUIPMENT_CATEGORY,
    ADVERTISING_EQUIPMENT_CATEGORY
)


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


def _get_inspection_items_for_room(room):
    inspection_items = []
    latest_record_sq = db.session.query(
        ProcurementRecord.item_id,
        func.max(ProcurementRecord.id).label('latest_record_id')
    ).group_by(ProcurementRecord.item_id).subquery()
    procurement_items = ProcurementDetail.query.join(
        latest_record_sq,
        ProcurementDetail.id == latest_record_sq.c.item_id
    ).join(
        ProcurementRecord,
        ProcurementRecord.id == latest_record_sq.c.latest_record_id
    ).join(
        ProcurementCategory,
        ProcurementCategory.id == ProcurementDetail.category_id
    ).filter(
        ProcurementRecord.location_id == room.id,
        ProcurementCategory.category.in_(MAINTENANCE_PROCUREMENT_CATEGORIES)
    ).order_by(ProcurementDetail.name.asc()).all()

    for item in procurement_items:
        inspection_items.append({
            'key': f'procurement-{item.id}',
            'id': item.id,
            'name': item.name,
            'equipment_type': item.category.category if item.category else 'อุปกรณ์',
            'erp_code': item.erp_code,
            'serial_number': item.serial_no,
            'source': 'procurement'
        })

    room_equipment = MaintenanceRoomEquipment.query.join(
        MaintenanceEquipmentType,
        MaintenanceEquipmentType.id == MaintenanceRoomEquipment.equipment_type_id
    ).filter(
        MaintenanceRoomEquipment.room_id == room.id
    ).order_by(MaintenanceRoomEquipment.equipment_name.asc()).all()
    for item in room_equipment:
        inspection_items.append({
            'key': f'maintenance-{item.id}',
            'id': item.id,
            'name': item.equipment_name,
            'equipment_type': item.equipment_type.name,
            'erp_code': None,
            'serial_number': item.serial_number,
            'source': 'maintenance'
        })

    procurement_ids = [item['id'] for item in inspection_items if item['source'] == 'procurement']
    procurement_key_by_erp_code = {
        item['erp_code']: item['key']
        for item in inspection_items
        if item['source'] == 'procurement' and item['erp_code']
    }
    inspection_item_keys = {item['key'] for item in inspection_items}
    room_equipment_ids = [item['id'] for item in inspection_items if item['source'] == 'maintenance']
    if procurement_ids or room_equipment_ids:
        history_filters = []
        if procurement_ids:
            history_filters.append(MaintenanceInspectionItem.procurement_detail_id.in_(procurement_ids))
        if procurement_key_by_erp_code:
            history_filters.append(
                MaintenanceInspectionItem.erp_code_snapshot.in_(procurement_key_by_erp_code.keys())
            )
        if room_equipment_ids:
            history_filters.append(MaintenanceInspectionItem.room_equipment_id.in_(room_equipment_ids))
        latest_history = {}
        history_rows = MaintenanceInspectionItem.query.filter(
            or_(*history_filters)
        ).order_by(
            MaintenanceInspectionItem.checked_at.desc(),
            MaintenanceInspectionItem.id.desc()
        ).all()
        for history in history_rows:
            key = (
                f'procurement-{history.procurement_detail_id}'
                if history.procurement_detail_id else f'maintenance-{history.room_equipment_id}'
            )
            if key not in inspection_item_keys:
                key = procurement_key_by_erp_code.get(history.erp_code_snapshot, key)
            if key not in latest_history:
                latest_history[key] = history
        for item in inspection_items:
            history = latest_history.get(item['key'])
            item['last_result'] = history.result if history else None
            checked_at = (
                arrow.get(history.checked_at, 'Asia/Bangkok').to('Asia/Bangkok')
                if history and history.checked_at else None
            )
            item['last_checked_at'] = (
                checked_at.strftime('%d/%m/%Y %H:%M') if checked_at else None
            )
            item['last_remark'] = history.remark if history else None
            item['last_inspector_name'] = (
                history.inspector.fullname
                if history and history.inspector and history.inspector.personal_info
                else (history.inspector.email if history and history.inspector else None)
            )

    return inspection_items


@maintenancebp.route('/items-check', methods=['GET', 'POST'])
@login_required
def maintenance_items_check():
    room_id = request.args.get('room_id', type=int)
    room = RoomResource.query.get_or_404(room_id) if room_id else None
    room_label = f'{room.number} {room.location}' if room else 'ทุกห้อง'
    inspection_items = _get_inspection_items_for_room(room) if room else []

    if request.method == 'POST':
        item_by_key = {item['key']: item for item in inspection_items}
        selected_keys = list(dict.fromkeys(request.form.getlist('checked_items')))
        selected_items = []
        errors = []

        if not selected_keys:
            errors.append('กรุณาเลือกอุปกรณ์ที่พร้อมตรวจอย่างน้อย 1 รายการ')

        for key in selected_keys:
            item = item_by_key.get(key)
            result = request.form.get(f'result-{key}')
            remark = request.form.get(f'remark-{key}', '', type=str).strip() or None
            if not item:
                errors.append('พบรายการอุปกรณ์ไม่ถูกต้อง')
                continue
            if result not in ('normal', 'issue'):
                errors.append(f'กรุณาเลือกผลการตรวจของ {item["name"]}')
                continue
            if result == 'issue' and not remark:
                errors.append(f'กรุณาระบุหมายเหตุของ {item["name"]}')
                continue
            selected_items.append((item, result, remark))

        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            submission = MaintenanceInspectionSubmission(
                room_id=room.id,
                submitted_by_id=current_user.id,
                submitted_at=arrow.now('Asia/Bangkok').datetime
            )
            db.session.add(submission)
            db.session.flush()
            for item, result, remark in selected_items:
                inspection_item = MaintenanceInspectionItem(
                    submission_id=submission.id,
                    inspector_id=current_user.id,
                    result=result,
                    remark=remark,
                    equipment_name_snapshot=item['name'],
                    equipment_type_snapshot=item['equipment_type'],
                    erp_code_snapshot=item['erp_code'],
                    serial_number_snapshot=item['serial_number'],
                    checked_at=arrow.now('Asia/Bangkok').datetime
                )
                if item['source'] == 'procurement':
                    inspection_item.procurement_detail_id = item['id']
                else:
                    inspection_item.room_equipment_id = item['id']
                db.session.add(inspection_item)
            db.session.commit()
            flash('บันทึกรายงานผลการตรวจเช็คเรียบร้อยแล้ว', 'success')
            return redirect(url_for('maintenance.maintenance_items_check', room_id=room.id))

    return render_template(
        'maintenance/maintenance_items_check.html',
        room=room,
        room_label=room_label,
        inspection_items=inspection_items
    )


@maintenancebp.route('/admin/equipment-types', methods=['GET', 'POST'])
def maintenance_equipment_types_admin():
    if request.method == 'POST':
        name = request.form.get('name', '', type=str).strip()
        sort_order = request.form.get('sort_order', 0, type=int) or 0

        if not name:
            flash('กรุณากรอกชื่อประเภทอุปกรณ์', 'danger')
        elif MaintenanceEquipmentType.query.filter_by(name=name).first():
            flash('มีประเภทอุปกรณ์นี้อยู่แล้ว', 'danger')
        else:
            db.session.add(MaintenanceEquipmentType(
                name=name,
                sort_order=sort_order,
                is_active=True
            ))
            db.session.commit()
            flash('เพิ่มประเภทอุปกรณ์เรียบร้อยแล้ว', 'success')
            return redirect(url_for('maintenance.maintenance_equipment_types_admin'))

    equipment_types = MaintenanceEquipmentType.query.order_by(
        MaintenanceEquipmentType.sort_order.asc(),
        MaintenanceEquipmentType.name.asc()
    ).all()
    return render_template(
        'maintenance/maintenance_equipment_types_admin.html',
        equipment_types=equipment_types
    )


@maintenancebp.route('/admin/equipment-types/<int:equipment_type_id>/edit', methods=['POST'])
def edit_maintenance_equipment_type(equipment_type_id):
    equipment_type = MaintenanceEquipmentType.query.get_or_404(equipment_type_id)
    name = request.form.get('name', '', type=str).strip()
    sort_order = request.form.get('sort_order', 0, type=int) or 0

    duplicate = MaintenanceEquipmentType.query.filter(
        MaintenanceEquipmentType.name == name,
        MaintenanceEquipmentType.id != equipment_type.id
    ).first()
    if not name:
        flash('กรุณากรอกชื่อประเภทอุปกรณ์', 'danger')
    elif duplicate:
        flash('มีประเภทอุปกรณ์นี้อยู่แล้ว', 'danger')
    else:
        equipment_type.name = name
        equipment_type.sort_order = sort_order
        equipment_type.is_active = 'is_active' in request.form
        db.session.commit()
        flash('แก้ไขประเภทอุปกรณ์เรียบร้อยแล้ว', 'success')

    return redirect(url_for('maintenance.maintenance_equipment_types_admin'))


@maintenancebp.route('/admin/equipment-types/<int:equipment_type_id>/delete', methods=['POST'])
def delete_maintenance_equipment_type(equipment_type_id):
    equipment_type = MaintenanceEquipmentType.query.get_or_404(equipment_type_id)
    if equipment_type.room_equipment.count():
        flash('ไม่สามารถลบประเภทอุปกรณ์ที่มีรายการอุปกรณ์ใช้งานอยู่', 'danger')
    else:
        db.session.delete(equipment_type)
        db.session.commit()
        flash('ลบประเภทอุปกรณ์เรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_equipment_types_admin'))


@maintenancebp.route('/list-item', methods=['GET', 'POST'])
def maintenance_list_item():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    room_id = request.args.get('room_id', type=int)
    per_page = 10

    latest_record_sq = db.session.query(
        ProcurementRecord.item_id,
        func.max(ProcurementRecord.id).label('latest_record_id')
    ).group_by(ProcurementRecord.item_id).subquery()

    room = None
    query = ProcurementDetail.query.join(
        latest_record_sq,
        ProcurementDetail.id == latest_record_sq.c.item_id
    ).join(
        ProcurementRecord,
        ProcurementRecord.id == latest_record_sq.c.latest_record_id
    ).join(
        ProcurementCategory,
        ProcurementCategory.id == ProcurementDetail.category_id
    ).filter(
        ProcurementCategory.category.in_(MAINTENANCE_PROCUREMENT_CATEGORIES)
    )
    if room_id:
        room = RoomResource.query.get_or_404(room_id)
        query = query.filter(ProcurementRecord.location_id == room.id)

    if request.method == 'POST':
        equipment_type_id = request.form.get('equipment_type_id', type=int)
        equipment_name = request.form.get('equipment_name', '', type=str).strip()
        serial_number = request.form.get('serial_number', '', type=str).strip() or None
        equipment_type = None

        if not room:
            flash('กรุณาเลือกห้องก่อนเพิ่มอุปกรณ์', 'danger')
        elif not equipment_type_id:
            flash('กรุณาเลือกประเภทอุปกรณ์', 'danger')
        elif not equipment_name:
            flash('กรุณากรอกชื่ออุปกรณ์', 'danger')
        else:
            equipment_type = MaintenanceEquipmentType.query.filter_by(
                id=equipment_type_id,
                is_active=True
            ).first()
            if not equipment_type:
                flash('ไม่พบประเภทอุปกรณ์ที่เลือก', 'danger')

        if room and equipment_type and equipment_name:
            db.session.add(MaintenanceRoomEquipment(
                room_id=room.id,
                equipment_type_id=equipment_type.id,
                equipment_name=equipment_name,
                serial_number=serial_number
            ))
            db.session.commit()
            flash('บันทึกอุปกรณ์เรียบร้อยแล้ว', 'success')
            return redirect(url_for('maintenance.maintenance_list_item', room_id=room.id))

    room_label = f'{room.number} {room.location}' if room else 'รายการครุภัณฑ์ทั้งหมด'

    if q:
        query = query.filter(or_(
            ProcurementDetail.name.ilike(f'%{q}%'),
            ProcurementDetail.erp_code.ilike(f'%{q}%'),
            ProcurementDetail.serial_no.ilike(f'%{q}%')
        ))

    maintenance_query = MaintenanceRoomEquipment.query.join(
        MaintenanceEquipmentType,
        MaintenanceEquipmentType.id == MaintenanceRoomEquipment.equipment_type_id
    )
    if room:
        maintenance_query = maintenance_query.filter(MaintenanceRoomEquipment.room_id == room.id)
    if q:
        maintenance_query = maintenance_query.filter(or_(
            MaintenanceRoomEquipment.equipment_name.ilike(f'%{q}%'),
            MaintenanceRoomEquipment.serial_number.ilike(f'%{q}%')
        ))

    procurement_rows = query.with_entities(
        ProcurementDetail.id.label('id'),
        ProcurementDetail.name.label('equipment_name'),
        ProcurementDetail.serial_no.label('serial_number'),
        ProcurementCategory.category.label('equipment_type'),
        ProcurementDetail.erp_code.label('erp_code'),
        literal('procurement').label('source')
    )
    maintenance_rows = maintenance_query.with_entities(
        MaintenanceRoomEquipment.id.label('id'),
        MaintenanceRoomEquipment.equipment_name.label('equipment_name'),
        MaintenanceRoomEquipment.serial_number.label('serial_number'),
        MaintenanceEquipmentType.name.label('equipment_type'),
        cast(None, String).label('erp_code'),
        literal('maintenance').label('source')
    )
    combined_rows = procurement_rows.union_all(maintenance_rows).subquery()
    pagination = db.session.query(combined_rows).order_by(
        combined_rows.c.equipment_name.asc(),
        combined_rows.c.id.asc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    equipment_types = MaintenanceEquipmentType.query.filter_by(is_active=True).order_by(
        MaintenanceEquipmentType.sort_order.asc(),
        MaintenanceEquipmentType.name.asc()
    ).all()
    return render_template(
        'maintenance/maintenance_list_item.html',
        pagination=pagination,
        q=q,
        room=room,
        room_label=room_label,
        room_query=room.id if room else None,
        equipment_types=equipment_types
    )


@maintenancebp.route('/room-equipment/<int:equipment_id>/delete', methods=['POST'])
def delete_maintenance_room_equipment(equipment_id):
    equipment = MaintenanceRoomEquipment.query.get_or_404(equipment_id)
    room_id = equipment.room_id
    submission_ids = {
        item.submission_id for item in equipment.inspection_items.all()
    }

    for inspection_item in equipment.inspection_items.all():
        db.session.delete(inspection_item)

    # Remove inspection headers only when no inspected equipment remains in them.
    db.session.flush()
    for submission_id in submission_ids:
        submission = MaintenanceInspectionSubmission.query.get(submission_id)
        if submission and not submission.items.count():
            db.session.delete(submission)

    db.session.delete(equipment)
    db.session.commit()
    flash('ลบอุปกรณ์และประวัติการตรวจเช็คที่เกี่ยวข้องเรียบร้อยแล้ว', 'success')
    return redirect(url_for('maintenance.maintenance_list_item', room_id=room_id))


@maintenancebp.route('/scan-room')
def maintenance_scan_room():
    return render_template(
        'maintenance/maintenance_scan_room.html'
    )


@maintenancebp.route('/system-check-design')
def maintenance_system_check_design():
    return render_template('maintenance/maintenance_system_check_design.html')


@maintenancebp.route('/room-system-equipment-design')
def maintenance_room_system_equipment_design():
    return render_template('maintenance/maintenance_room_system_equipment_design.html')


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
        db.session.add(new_link)
        db.session.commit()
        flash('บันทึกการผูกครุภัณฑ์เข้ากับระบบตรวจเช็คเรียบร้อยแล้ว', 'success')

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


@maintenancebp.route('/scan-add-item/lookup')
def maintenance_scan_add_item_lookup():
    scan_code = request.args.get('code', '', type=str).strip()
    if not scan_code:
        return jsonify({'message': 'QR Code ไม่ถูกต้อง'}), 400

    item = ProcurementDetail.query.filter(or_(
        ProcurementDetail.procurement_no == scan_code,
        ProcurementDetail.erp_code == scan_code
    )).first()
    if not item:
        return jsonify({'message': 'ไม่พบข้อมูลครุภัณฑ์'}), 404

    return jsonify({
        'erp_code': item.erp_code or '',
        'name': item.name or ''
    })
