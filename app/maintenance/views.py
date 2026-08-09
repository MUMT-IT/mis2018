from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import String, cast, func, literal, or_
import arrow

from app.main import db
from app.maintenance.models import (
    MaintenanceEquipmentType,
    MaintenanceInspectionItem,
    MaintenanceInspectionSubmission,
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


def _inspection_type_key(equipment_type, equipment_name=''):
    equipment_type = (equipment_type or '').lower()
    equipment_name = (equipment_name or '').lower()
    equipment_text = f'{equipment_type} {equipment_name}'
    if 'คอมพิวเตอร์' in equipment_text:
        return 'computer'
    if 'ไมโครโฟน' in equipment_text or 'ไมค์' in equipment_text:
        return 'microphone'
    if 'เสียง' in equipment_text:
        return 'audio'
    if any(keyword in equipment_text for keyword in (
        'จอ', 'แสดงภาพ', 'projector', 'โปรเจคเตอร์', 'โปรเจ็กเตอร์', 'monitor', 'tv'
    )):
        return 'display'
    return None


def _get_latest_room_inspection_statuses(room_ids):
    statuses = {room_id: {} for room_id in room_ids}
    if not room_ids:
        return statuses

    rows = db.session.query(
        MaintenanceInspectionSubmission.room_id,
        MaintenanceInspectionItem
    ).join(
        MaintenanceInspectionItem,
        MaintenanceInspectionItem.submission_id == MaintenanceInspectionSubmission.id
    ).filter(
        MaintenanceInspectionSubmission.room_id.in_(room_ids)
    ).order_by(
        MaintenanceInspectionItem.checked_at.desc(),
        MaintenanceInspectionItem.id.desc()
    ).all()
    for room_id, item in rows:
        equipment_key = _inspection_type_key(
            item.equipment_type_snapshot,
            item.equipment_name_snapshot
        )
        if equipment_key and equipment_key not in statuses[room_id]:
            days_since = 0
            checked_at = None
            if item.checked_at:
                checked_at = arrow.get(item.checked_at, 'Asia/Bangkok').to('Asia/Bangkok')
                days_since = max(
                    0,
                    (arrow.now('Asia/Bangkok').date() - checked_at.date()).days
                )
            statuses[room_id][equipment_key] = {
                'result': item.result,
                'checked_at': checked_at.strftime('%d/%m/%Y') if checked_at else '-',
                'remark': item.remark,
                'days_since': days_since,
                'is_overdue': days_since > 30
            }
    return statuses


def _get_room_inspection_alert_summaries():
    rows = db.session.query(
        MaintenanceInspectionSubmission.room_id,
        MaintenanceInspectionItem
    ).join(
        MaintenanceInspectionItem,
        MaintenanceInspectionItem.submission_id == MaintenanceInspectionSubmission.id
    ).order_by(
        MaintenanceInspectionItem.checked_at.desc(),
        MaintenanceInspectionItem.id.desc()
    ).all()

    latest_items = {}
    for room_id, item in rows:
        if item.procurement_detail_id:
            equipment_key = f'procurement-{item.procurement_detail_id}'
        elif item.room_equipment_id:
            equipment_key = f'maintenance-{item.room_equipment_id}'
        elif item.erp_code_snapshot:
            equipment_key = f'erp-{item.erp_code_snapshot}'
        else:
            equipment_key = f'snapshot-{item.equipment_type_snapshot}-{item.equipment_name_snapshot}'

        latest_items.setdefault((room_id, equipment_key), item)

    room_ids = {room_id for room_id, _ in latest_items}
    room_labels = {
        room.id: f'{room.number} {room.location}'
        for room in RoomResource.query.filter(RoomResource.id.in_(room_ids)).all()
    } if room_ids else {}
    overdue_counts = {}
    issue_counts = {}
    today = arrow.now('Asia/Bangkok').date()

    for (room_id, _), item in latest_items.items():
        if item.checked_at:
            checked_at = arrow.get(item.checked_at, 'Asia/Bangkok').to('Asia/Bangkok')
            days_since = max(0, (today - checked_at.date()).days)
            if days_since > 30:
                overdue_counts[room_id] = overdue_counts.get(room_id, 0) + 1
        if item.result == 'issue':
            issue_counts[room_id] = issue_counts.get(room_id, 0) + 1

    def build_summary(counts):
        return [
            {'room': room_labels.get(room_id, str(room_id)), 'count': count}
            for room_id, count in sorted(counts.items(), key=lambda entry: entry[0])
        ]

    return build_summary(overdue_counts), build_summary(issue_counts)


@maintenancebp.route('/list-room')
def maintenance_list_room():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    per_page = 10

    query = RoomResource.query
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
    room_statuses = _get_latest_room_inspection_statuses(
        [room.id for room in pagination.items]
    )
    overdue_room_summaries, issue_room_summaries = _get_room_inspection_alert_summaries()
    return render_template(
        'maintenance/maintenance_list_room.html',
        pagination=pagination,
        q=q,
        room_statuses=room_statuses,
        overdue_room_summaries=overdue_room_summaries,
        issue_room_summaries=issue_room_summaries
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
