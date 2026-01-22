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
        messages = []
        new_province_count = 0
        updated_province_count = 0
        skipped_row_count = 0
        file = request.files['file']
        if file and allowed_file(file.filename):
            df = read_excel(file, dtype='object')
            for idx, rec in df.iterrows():
                row_number = idx + 2
                row_messages = []
                try:
                    order_id, name, code = rec
                except ValueError:
                    row_messages.append(f"แถวที่ {row_number}")
                    messages.append({"type": "error", "message": "; ".join(row_messages)})
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
                        row_messages.append(f"ไม่สามารถเพิ่มจังหวัดใหม่ได้: {e}")
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
                        row_messages.append(f"ไม่สามารถอัปเดตข้อมูลจังหวัดได้: {e}")
                        skipped_row_count += 1

                    messages.append(
                        {"type": "error", "message": f"แถวที่ {row_number}: {'; '.join(row_messages)}"})
            if row_messages:
                for msg in messages:
                    flash(msg["message"], msg["type"])
            flash(f"--- สรุปผลการนำเข้าข้อมูล ---", 'info')
            flash(f"เพิ่มจังหวัด: {new_province_count} จังหวัด", 'success')
            flash(f"อัปเดตข้อมูลจังหวัด: {updated_province_count} จังหวัด", 'success')
            flash(f"ข้ามการประมวลผล: {skipped_row_count} แถว (โปรดดูรายละเอียดในข้อความแจ้งเตือนด้านบน)", 'warning')
            return render_template('address/upload_province.html')
    return render_template('address/upload_province.html')


@address.route('/district/index', methods=['GET', 'POST'])
def upload_district():
    if request.method == 'POST':
        messages = []
        new_district_count = 0
        updated_district_count = 0
        skipped_row_count = 0
        file = request.files['file']
        if file and allowed_file(file.filename):
            df = read_excel(file, dtype='object')
            for idx, rec in df.iterrows():
                row_number = idx + 2
                row_messages = []
                try:
                    order_id, name, code, province_name = rec
                except ValueError:
                    row_messages.append(f"แถวที่ {row_number}")
                    messages.append({"type": "error", "message": "; ".join(row_messages)})
                    skipped_row_count += 1
                    continue
                str_code = str(code)
                district = District.query.filter_by(name=name, code=str_code).first()
                province = Province.query.filter_by(name=province_name).first()
                if not district:
                    try:
                        new_district = District(order_id=order_id, name=name, code=str_code, province_id=province.id)
                        db.session.add(new_district)
                        db.session.commit()
                        new_district_count += 1
                    except Exception as e:
                        db.session.rollback()
                        row_messages.append(f"ไม่สามารถเพิ่มอำเภอใหม่ได้: {e}")
                        skipped_row_count += 1
                else:
                    try:
                        district.order_id = order_id if order_id is not None else district.order_id
                        district.name = name if name is not None else district.name
                        district.code = str_code if str_code is not None else district.code
                        district.province_id = province.id if province else district.province_id
                        db.session.add(province)
                        db.session.commit()
                        updated_district_count += 1
                    except Exception as e:
                        db.session.rollback()
                        row_messages.append(f"ไม่สามารถอัปเดตข้อมูลอำเภอได้: {e}")
                        skipped_row_count += 1

                    messages.append(
                        {"type": "error", "message": f"แถวที่ {row_number}: {'; '.join(row_messages)}"})

            if row_messages:
                for msg in messages:
                    flash(msg["message"], msg["type"])
            flash(f"--- สรุปผลการนำเข้าข้อมูล ---", 'info')
            flash(f"เพิ่มอำเภอ: {new_district_count} อำเภอ", 'success')
            flash(f"อัปเดตข้อมูลอำเภอ: {updated_district_count} อำเภอ", 'success')
            flash(f"ข้ามการประมวลผล: {skipped_row_count} แถว (โปรดดูรายละเอียดในข้อความแจ้งเตือนด้านบน)", 'warning')
            return render_template('address/upload_district.html')
    return render_template('address/upload_district.html')


@address.route('/subdistrict/index', methods=['GET', 'POST'])
def upload_subdistrict():
    if request.method == 'POST':
        messages = []
        new_subdistrict_count = 0
        updated_subdistrict_count = 0
        skipped_row_count = 0
        file = request.files['file']
        if file and allowed_file(file.filename):
            df = read_excel(file, dtype='object')
            for idx, rec in df.iterrows():
                row_number = idx + 2
                row_messages = []
                try:
                    order_id, name, code, district_name, district_code, zip_code = rec
                except ValueError:
                    row_messages.append(f"แถวที่ {row_number}")
                    messages.append({"type": "error", "message": "; ".join(row_messages)})
                    skipped_row_count += 1
                    continue
                str_code = str(code)
                str_district_code = str(district_code)
                subdistrict = Subdistrict.query.filter_by(name=name, code=str_code).first()
                district = District.query.filter_by(name=district_name, code=str_district_code).first()
                zipcode = Zipcode.query.filter_by(zip_code=zip_code).first()
                if not zipcode:
                    zipcode = Zipcode(zip_code=zip_code)
                    db.session.add(zipcode)
                    db.session.commit()
                if not subdistrict:
                    try:
                        new_subdistrict = Subdistrict(order_id=order_id, name=name, code=str_code, district_id=district.id,
                                                   zip_code_id=zipcode.id)
                        db.session.add(new_subdistrict)
                        db.session.commit()
                        new_subdistrict_count += 1
                    except Exception as e:
                        db.session.rollback()
                        row_messages.append(f"ไม่สามารถเพิ่มตำบลใหม่ได้: {e}")
                        skipped_row_count += 1
                else:
                    try:
                        subdistrict.order_id = order_id if order_id is not None else subdistrict.order_id
                        subdistrict.name = name if name is not None else subdistrict.name
                        subdistrict.code = str_code if str_code is not None else subdistrict.code
                        subdistrict.district_id = district.id if district else subdistrict.province_id
                        subdistrict.zip_code_id = zipcode.id if zipcode else subdistrict.zip_pcode_id
                        db.session.add(subdistrict)
                        db.session.commit()
                        updated_subdistrict_count += 1
                    except Exception as e:
                        db.session.rollback()
                        row_messages.append(f"ไม่สามารถอัปเดตข้อมูลตำบลได้: {e}")
                        skipped_row_count += 1

                    messages.append(
                        {"type": "error", "message": f"แถวที่ {row_number}: {'; '.join(row_messages)}"})

            if row_messages:
                for msg in messages:
                    flash(msg["message"], msg["type"])

            flash(f"--- สรุปผลการนำเข้าข้อมูล ---", 'info')
            flash(f"เพิ่มผตำบล: {new_subdistrict_count} ตำบล", 'success')
            flash(f"อัปเดตข้อมูลตำบล: {updated_subdistrict_count} ตำบล", 'success')
            flash(f"ข้ามการประมวลผล: {skipped_row_count} แถว (โปรดดูรายละเอียดในข้อความแจ้งเตือนด้านบน)", 'warning')
            return render_template('address/upload_subdistrict.html')
    return render_template('address/upload_subdistrict.html')