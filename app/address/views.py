from flask import request, render_template, flash
from app.address import address
from pandas import read_excel, isna
from app.models import *

ALLOWED_EXTENSIONS = ['xlsx', 'xls']


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@address.route('/index')
def index():
    return render_template('address/index.html')


@address.route('/province/index', methods=['GET', 'POST'])
def upload_province():
    if request.method == 'POST':
        new_province_count = 0
        updated_province_count = 0
        skipped_row_count = 0
        file = request.files['file']
        if file and allowed_file(file.filename):
            df = read_excel(file, dtype='object')
            for idx, rec in df.iterrows():
                try:
                    order_id, name, code = rec
                except ValueError:
                    skipped_row_count += 1
                    continue
                str_code = str(code)
                province = Province.query.filter_by(name=name, code=str_code).first()
                if not province:
                    try:
                        new_province = Province(order_id=order_id, name=name, code=str_code)
                        db.session.add(new_province)
                        db.session.commit()
                        new_province_count += 1
                    except Exception as e:
                        db.session.rollback()
                        skipped_row_count += 1
                else:
                    try:
                        province.order_id = order_id if order_id is not None else province.order_id
                        province.name = name if name is not None else province.name
                        province.code = str_code if str_code is not None else province.code
                        db.session.add(province)
                        db.session.commit()
                        updated_province_count += 1
                    except Exception as e:
                        db.session.rollback()
                        skipped_row_count += 1
            flash(f"--- สรุปผลการนำเข้าข้อมูล ---", 'info')
            flash(f"เพิ่มผู้รับบริการ: {new_province_count} คน", 'success')
            flash(f"อัปเดตข้อมูลผู้รับบริการ: {updated_province_count} คน", 'success')
            flash(f"ข้ามการประมวลผล: {skipped_row_count} แถว (โปรดดูรายละเอียดในข้อความแจ้งเตือนด้านบน)", 'warning')
            return render_template('address/upload_province.html')
    return render_template('address/upload_province.html')


@address.route('/district/index', methods=['GET', 'POST'])
def upload_province():
    if request.method == 'POST':
        new_province_count = 0
        updated_province_count = 0
        skipped_row_count = 0
        file = request.files['file']
        if file and allowed_file(file.filename):
            df = read_excel(file, dtype='object')
            for idx, rec in df.iterrows():
                try:
                    order_id, name, code = rec
                except ValueError:
                    skipped_row_count += 1
                    continue
                str_code = str(code)
                province = Province.query.filter_by(name=name, code=str_code).first()
                if not province:
                    try:
                        new_province = Province(order_id=order_id, name=name, code=str_code)
                        db.session.add(new_province)
                        db.session.commit()
                        new_province_count += 1
                    except Exception as e:
                        db.session.rollback()
                        skipped_row_count += 1
                else:
                    try:
                        province.order_id = order_id if order_id is not None else province.order_id
                        province.name = name if name is not None else province.name
                        province.code = str_code if str_code is not None else province.code
                        db.session.add(province)
                        db.session.commit()
                        updated_province_count += 1
                    except Exception as e:
                        db.session.rollback()
                        skipped_row_count += 1
            flash(f"--- สรุปผลการนำเข้าข้อมูล ---", 'info')
            flash(f"เพิ่มผู้รับบริการ: {new_province_count} คน", 'success')
            flash(f"อัปเดตข้อมูลผู้รับบริการ: {updated_province_count} คน", 'success')
            flash(f"ข้ามการประมวลผล: {skipped_row_count} แถว (โปรดดูรายละเอียดในข้อความแจ้งเตือนด้านบน)", 'warning')
            return render_template('address/upload_province.html')
    return render_template('address/upload_province.html')