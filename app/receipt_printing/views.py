# -*- coding:utf-8 -*-
import os
from datetime import datetime

import pytz
import requests
from bahttext import bahttext
from flask import render_template, request, flash, redirect, url_for, send_file, send_from_directory, make_response, \
    jsonify
from flask_login import current_user, login_required
from pandas import DataFrame
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, TableStyle, Table, Spacer, PageBreak
from werkzeug.utils import secure_filename
from pydrive.auth import GoogleAuth
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.drive import GoogleDrive
from flask_mail import Message
from ..main import mail
from sqlalchemy import cast, Date, and_

from . import receipt_printing_bp as receipt_printing
from .forms import *
from .models import *
from ..comhealth.models import ComHealthReceiptID
from ..main import db
from ..roles import finance_permission, finance_head_permission

bangkok = pytz.timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = ['xlsx', 'xls']

FOLDER_ID = "1k_k0fAKnEEZaO3fhKwTLhv2_ONLam0-c"

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()


ALLOWED_EXTENSION = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


@receipt_printing.route('/index')
@finance_permission.require()
def index():
    return render_template('receipt_printing/index.html')


@receipt_printing.route('/landing')
def landing():
    return render_template('receipt_printing/landing.html')


@receipt_printing.route('/receipt/create', methods=['POST', 'GET'])
def create_receipt():
    form = ReceiptDetailForm()
    receipt_book = ComHealthReceiptID.query.filter_by(code='MTG').first()
    form_list = ReceiptListForm()
    if form.validate_on_submit():
        receipt_detail = ElectronicReceiptDetail()
        receipt_detail.issuer = current_user
        receipt_detail.created_datetime = datetime.now(tz=bangkok)
        form.populate_obj(receipt_detail)  #insert data from Form to Model
        receipt_detail.number = receipt_book.next
        receipt_book.count += 1
        receipt_detail.book_number = receipt_book.book_number
        db.session.add(receipt_detail)
        db.session.commit()
        flash(u'บันทึกการสร้างใบเสร็จรับเงินสำเร็จ.', 'success')
        return redirect(url_for('receipt_printing.view_receipt_by_list_type'))
    # Check Error
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('receipt_printing/new_receipt.html', form=form, form_list=form_list)


@receipt_printing.route('/receipt/add-items', methods=['POST'])
def list_add_items():
    form = ReceiptListForm()
    if form.validate_on_submit():
        return u'''
        <tr>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
        </tr>
    '''.format(form.item.data,
               form.price.data,
               form.gl.data,
               form.cost_center.data,
               form.internal_order_code.data
               # form.item(class_="input", hidden=True),
               # form.price(class_="input", placeholder=u"฿", hidden=True),
               # form.gl(class_="select", hidden=True),
               # form.cost_center(class_="select", hidden=True),
               # form.internal_order_code(class_="select", hidden=True)
               )
# @receipt_printing.route('/receipt/create/add-items', methods=['POST', 'GET'])
# def list_add_items():
#     form = ReceiptDetailForm()
#     form.items.append_entry()
#     item_form = form.items[-1]
#     form_text = '<table class="table is-bordered is-fullwidth is-narrow">'
#     form_text += u'''
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="control">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="control">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="select">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="select">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="select">
#             {}
#         </div>
#     </div>
#     '''.format(item_form.item.label, item_form.item(class_="input"), item_form.price.label,
#                item_form.price(class_="input", placeholder=u"฿",
#                                **{'hx-post': url_for("receipt_printing.update_amount"),
#                                   'hx-trigger': 'keyup changed delay:500ms', 'hx-target': '#paid_amount',
#                                   'hx-swap': 'outerHTML'}),
#                item_form.gl.label, item_form.gl(class_="select"),
#                item_form.cost_center.label, item_form.cost_center(class_="select"),
#                item_form.internal_order_code.label, item_form.internal_order_code(class_="select")
#                )
#     resp = make_response(form_text)
#     resp.headers['HX-Trigger-After-Swap'] = 'update_amount'
#     return resp


@receipt_printing.route('/receipt/create/update-amount', methods=['POST'])
def update_amount():
    form = ReceiptDetailForm()
    total_amount = 0.0
    for item in form.items.entries:
        total_amount += float(item.price.data)
    return form.paid_amount(class_="input", readonly=True, value=total_amount)


# @receipt_printing.route('/receipt/create/items-delete', methods=['POST', 'GET'])
# def delete_items():
#     form = ReceiptDetailForm()
#     if len(form.items.entries) > 1:
#         form.items.pop_entry()
#         alert = False
#     else:
#         alert = True
#     form_text = ''
#     for item_form in form.items.entries:
#         form_text += u'''
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="control">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="control">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="select">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="select">
#             {}
#         </div>
#     </div>
#     <div class="field">
#         <label class="label">{}</label>
#         <div class="select">
#             {}
#         </div>
#     </div>
#     '''.format(item_form.item.label, item_form.item(class_="input"), item_form.price.label,
#                item_form.price(class_="input", placeholder=u"฿",
#                                **{'hx-post': url_for("receipt_printing.update_amount"), 'hx-trigger': 'keyup changed delay:500ms',
#                                   'hx-target': '#paid_amount', 'hx-swap': 'outerHTML'}),
#                item_form.gl.label, item_form.gl(class_="select"),
#                item_form.cost_center.label, item_form.cost_center(class_="select"),
#                item_form.internal_order_code.label, item_form.internal_order_code(class_="select")
#                )
#
#     resp = make_response(form_text)
#     if alert:
#         resp.headers['HX-Trigger-After-Swap'] = 'delete_warning'
#     else:
#         resp.headers['HX-Trigger-After-Swap'] = 'update_amount'
#     return resp


@receipt_printing.route('/items/<int:item_id>/delete')
def delete_items(item_id):
    if item_id:
        item = ElectronicReceiptItem.query.get(item_id)
        flash(u'The items has been removed.')
        db.session.delete(item)
        db.session.commit()
        return redirect(url_for('receipt_printing.create_receipt', item_id=item_id))

# @receipt_printing.route('/list/receipts', methods=['GET'])
# def list_all_receipts():
#     record = ElectronicReceiptDetail.query.all()
#     return render_template('receipt_printing/list_all_receipts.html', record=record)


sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))


@receipt_printing.route('/receipts/pdf/<int:receipt_id>')
def export_receipt_pdf(receipt_id):
    receipt = ElectronicReceiptDetail.query.get(receipt_id)
    # if receipt.print_number >= 1:
    #     flash(u"ไม่สามารถพิมพ์ได้มากกว่า 1 ครั้ง", "danger")
    #     return redirect(url_for("receipt_printing.list_all_receipts"))

    def all_page_setup(canvas, doc):
        canvas.saveState()
        logo_image = ImageReader('app/static/img/mu-watermark.png')
        canvas.drawImage(logo_image, 140, 300, mask='auto')
        canvas.restoreState()

    doc = SimpleDocTemplate("app/receipt.pdf",
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=20,
                            bottomMargin=10,
                            )
    book_id = receipt.book_number
    receipt_number = receipt.number
    data = []
    affiliation = '''<para align=center><font size=10>
    </font></para>
    '''
    address = '''<font size=11>
    </font>
    '''

    receipt_info = '''<font size=15>
    {original}</font><br/><br/>
    <font size=11>
    เล่มที่/Book No.{book_id}<br/>
    เลขที่/No. {receipt_number}<br/>
    วันที่/Date {issued_date}
    </font>
    '''
    issued_date = datetime.now().strftime('%d/%m/%Y')
    receipt_info_ori = receipt_info.format(original=u'ต้นฉบับ<br/>(Original)'.encode('utf-8'),
                                           book_id=book_id,
                                           receipt_number=receipt_number,
                                           issued_date=issued_date,
                                           )

    receipt_info_copy = receipt_info.format(original=u'สำเนา<br/>(Copy)'.encode('utf-8'),
                                            book_id=book_id,
                                            receipt_number=receipt_number,
                                            issued_date=issued_date,
                                            )

    header_content_ori = [[Paragraph(address, style=style_sheet['ThaiStyle']),
                           [Paragraph(affiliation, style=style_sheet['ThaiStyle'])],
                           [],
                           Paragraph(receipt_info_ori, style=style_sheet['ThaiStyle'])]]

    header_content_copy = [[Paragraph(address, style=style_sheet['ThaiStyle']),
                            [Paragraph(affiliation, style=style_sheet['ThaiStyle'])],
                            [],
                            Paragraph(receipt_info_copy, style=style_sheet['ThaiStyle'])]]

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ])

    header_ori = Table(header_content_ori, colWidths=[150, 200, 50, 100])
    header_copy = Table(header_content_copy, colWidths=[150, 200, 50, 100])

    header_ori.hAlign = 'CENTER'
    header_ori.setStyle(header_styles)

    header_copy.hAlign = 'CENTER'
    header_copy.setStyle(header_styles)
    customer_name = '''<para><font size=12>
    ได้รับเงินจาก / RECEIVED FROM {received_from}<br/>
    ที่อยู่ / ADDRESS {address}
    </font></para>
    '''.format(received_from=receipt.received_from.encode('utf-8'),
               address=receipt.address.encode('utf-8'))

    customer = Table([[Paragraph(customer_name, style=style_sheet['ThaiStyle']),
                    ]],
                     colWidths=[580, 200]
                     )
    customer.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                  ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    items = [[Paragraph('<font size=10>ลำดับ / No.</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รายการ / Description</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวนเงิน / Amount</font>', style=style_sheet['ThaiStyleCenter']),
              ]]
    total = 0
    for n, item in enumerate(receipt.items, start=1):
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                Paragraph('<font size=12>{}</font>'.format(item.item.encode('utf-8')), style=style_sheet['ThaiStyle']),
                Paragraph('<font size=12>{:,.2f}</font>'.format(item.price), style=style_sheet['ThaiStyleNumber'])
                ]
        items.append(item_record)
        total += item.price

    n = len(items)
    for i in range(22-n):
        items.append([
            Paragraph('<font size=12>&nbsp; </font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12> </font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12> </font>', style=style_sheet['ThaiStyleNumber']),
        ])
    total_thai = bahttext(total)
    total_text = "รวมเงินทั้งสิ้น/ TOTAL : {}".format(total_thai.encode('utf-8'))
    items.append([
        Paragraph('<font size=12>{}</font>'.format(total_text), style=style_sheet['ThaiStyleNumber']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(total), style=style_sheet['ThaiStyleNumber'])
    ])
    item_table = Table(items, colWidths=[50, 450, 75])
    item_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, 0), 0.25, colors.black),
        ('BOX', (0, -1), (-1, -1), 0.25, colors.black),
        ('BOX', (0, 0), (0, -1), 0.25, colors.black),
        ('BOX', (1, 0), (1, -1), 0.25, colors.black),
        ('BOX', (2, 0), (2, -1), 0.25, colors.black),
        ('BOX', (3, 0), (3, -1), 0.25, colors.black),
        ('BOX', (4, 0), (4, -1), 0.25, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, -2), (-1, -2), 10),
    ]))
    item_table.setStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])
    item_table.setStyle([('SPAN', (0, -1), (1, -1))])

    if receipt.payment_method == u'เงินสด':
        payment_info = Paragraph('<font size=14>ชำระโดย / PAID BY: เงินสด / CASH</font>', style=style_sheet['ThaiStyle'])
    elif receipt.payment_method == u'บัตรเครดิต':
        payment_info = Paragraph('<font size=14>ชำระโดย / PAID BY: บัตรเครดิต / CREDIT CARD NUMBER {}-****-****-{}</font>'.format(receipt.card_number[:4], receipt.card_number[-4:]),
                                 style=style_sheet['ThaiStyle'])
    elif receipt.payment_method == u'Scan QR Code':
        payment_info = Paragraph('<font size=14>ชำระโดย / PAID BY: สแกนคิวอาร์โค้ด / SCAN QR CODE</font>', style=style_sheet['ThaiStyle'])
    elif receipt.payment_method == u'โอนผ่านระบบธนาคารอัตโนมัติ':
        payment_info = Paragraph('<font size=14>ชำระโดย / PAID BY: โอนผ่านระบบธนาคารอัตโนมัติ / TRANSFER TO BANK</font>',
                                 style=style_sheet['ThaiStyle'])
    elif receipt.payment_method == u'เช็คสั่งจ่าย':
        payment_info = Paragraph('<font size=14>ชำระโดย / PAID BY: เช็คสั่งจ่าย / CHEQUE NUMBER {}****</font>'.format(receipt.cheque_number[:4]),
                                 style=style_sheet['ThaiStyle'])
    else:
        payment_info = Paragraph('<font size=11>ยังไม่ชำระเงิน / UNPAID</font>', style=style_sheet['ThaiStyle'])

    total_content = [[payment_info,
                      Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
                      Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]

    total_table = Table(total_content, colWidths=[360, 150, 50])

    notice_text = '''<para align=center><font size=10>
    กรณีชำระด้วยเช็ค ใบเสร็จรับเงินฉบับนี้จะสมบูรณ์ต่อเมื่อ เรียกเก็บเงินได้ตามเช็คเรียบร้อยแล้ว <br/> If paying by cheque, a receipt will be completed upon receipt of the cheque complete.
    <br/>เอกสารนี้พิมพ์จากคอมพิวเตอร์</font></para>
    '''
    notice = Table([[Paragraph(notice_text, style=style_sheet['ThaiStyle'])]])

    sign_text = Paragraph('<br/><font size=12>............................................................................ ผู้รับเงิน / RECEIVING OFFICER<br/></font>',
                          style=style_sheet['ThaiStyle'])
    receive = [[sign_text,
                      Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
                      Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    receive_officer = Table(receive, colWidths=[0, 80, 20])

    fullname = Paragraph('<font size=12>({})<br/></font>'.format(receipt.issuer.personal_info.fullname.encode('utf-8')),
                         style=style_sheet['ThaiStyle'])
    personal_info = [[fullname,
                Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    issuer_personal_info = Table(personal_info, colWidths=[0, 30, 20])

    position = Paragraph('<font size=12>..............{}..................... ตำแหน่ง / POSITION </font>'.format(receipt.issuer.personal_info.position.encode('utf-8')),
                         style=style_sheet['ThaiStyle'])
    position_info = [[position,
                      Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    issuer_position = Table(position_info, colWidths=[0, 80, 20])

    cancel_text = '''<para align=right><font size=20 color=red>ยกเลิก {}</font></para>'''.format(receipt.number)
    cancel_receipts = Table([[Paragraph(cancel_text, style=style_sheet['ThaiStyle'])]])

    if receipt.cancelled:
        number_of_copies = 2 if receipt.copy_number == 1 else 1
        for i in range(number_of_copies):
            if i == 0 and receipt.copy_number == 1:
                data.append(header_ori)
                data.append(cancel_receipts)
            else:
                data.append(cancel_receipts)
                data.append(header_copy)

            data.append(customer)
            data.append(Spacer(1, 12))
            data.append(Spacer(1, 6))
            data.append(item_table)
            data.append(Spacer(1, 6))
            data.append(total_table)
            data.append(Spacer(1, 12))
            data.append(receive_officer)
            data.append(issuer_personal_info)
            data.append(issuer_position)
            data.append(Paragraph('เลขที่กำกับเอกสาร<br/> Regulatory Document No. {}'.format(receipt.book_number),
                                  style=style_sheet['ThaiStyle']))
            data.append(Paragraph('Time {}'.format(receipt.created_datetime.astimezone(bangkok).strftime('%H:%M:%S')),
                                  style=style_sheet['ThaiStyle']))
            data.append(notice)
            data.append(PageBreak())
    else:
        number_of_copies = 2 if receipt.copy_number == 1 else 1
        for i in range(number_of_copies):
            if i == 0 and receipt.copy_number == 1:
                data.append(header_ori)
            else:
                data.append(header_copy)

            data.append(customer)
            data.append(Spacer(1, 12))
            data.append(Spacer(1, 6))
            data.append(item_table)
            data.append(Spacer(1, 6))
            data.append(total_table)
            data.append(Spacer(1, 12))
            data.append(receive_officer)
            data.append(issuer_personal_info)
            data.append(issuer_position)
            data.append(Paragraph('เลขที่กำกับเอกสาร<br/> Regulatory Document No. {}'.format(receipt.book_number),
                                  style=style_sheet['ThaiStyle']))
            data.append(Paragraph('Time {}'.format(receipt.created_datetime.astimezone(bangkok).strftime('%H:%M:%S')),
                                  style=style_sheet['ThaiStyle']))
            data.append(notice)
            data.append(PageBreak())
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)

    receipt.print_number += 1
    db.session.add(receipt)
    db.session.commit()

    return send_file('receipt.pdf')


@receipt_printing.route('list/receipts/cancel')
def list_to_cancel_receipt():
    record = ElectronicReceiptDetail.query.filter_by(cancelled=True)
    return render_template('receipt_printing/list_to_cancel_receipt.html', record=record)


@receipt_printing.route('/receipts/cancel/confirm/<int:receipt_id>', methods=['GET', 'POST'])
def confirm_cancel_receipt(receipt_id):
    receipt = ElectronicReceiptDetail.query.get(receipt_id)
    if not receipt.cancelled:
        return render_template('receipt_printing/confirm_cancel_receipt.html', receipt=receipt)
    return redirect(url_for('receipt_printing.list_all_receipts'))


@receipt_printing.route('receipts/cancel/<int:receipt_id>', methods=['POST'])
def cancel_receipt(receipt_id):
    receipt = ElectronicReceiptDetail.query.get(receipt_id)
    receipt.cancelled = True
    receipt.cancel_comment = request.form.get('comment')
    db.session.add(receipt)
    db.session.commit()
    return redirect(url_for('receipt_printing.list_to_cancel_receipt'))


@receipt_printing.route('/daily/payment/report', methods=['GET', 'POST'])
def daily_payment_report():
    query = ElectronicReceiptDetail.query
    form = ReportDateForm()
    start_date = None
    end_date = None
    if request.method == 'POST':
        start_date, end_date = form.created_datetime.data.split(' - ')
        start_date = datetime.strptime(start_date, '%d-%m-%Y')
        end_date = datetime.strptime(end_date, '%d-%m-%Y')
        if start_date < end_date:
            query = query.filter(and_(ElectronicReceiptDetail.created_datetime >= start_date,
                                      ElectronicReceiptDetail.created_datetime <= end_date))
        else:
            query = query.filter(cast(ElectronicReceiptDetail.created_datetime, Date) == start_date)
    else:
        flash(form.errors, 'danger')
    start_date = start_date.strftime('%d-%m-%Y') if start_date else ''
    end_date = end_date.strftime('%d-%m-%Y') if end_date else ''
    return render_template('receipt_printing/daily_payment_report.html', records=query, form=form,
                           start_date=start_date, end_date=end_date)


@receipt_printing.route('/daily/payment/report/download')
def download_daily_payment_report():
    records = []
    query = ElectronicReceiptDetail.query
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date:
        start_date = datetime.strptime(start_date, '%d-%m-%Y')
        end_date = datetime.strptime(end_date, '%d-%m-%Y')
        if start_date < end_date:
            query = query.filter(and_(ElectronicReceiptDetail.created_datetime >= start_date,
                                      ElectronicReceiptDetail.created_datetime <= end_date))
        else:
            query = query.filter(cast(ElectronicReceiptDetail.created_datetime, Date) == start_date)

    for receipt in query:
        records.append({
            u'เล่มที่': u"{}".format(receipt.book_number),
            u'เลขที่': u"{}".format(receipt.number),
            u'รายการ': u"{}".format(receipt.item_list),
            u'ช่องทางการชำระเงิน': u"{}".format(receipt.payment_method),
            u'เลขที่บัตรเครดิต': u"{}".format(receipt.card_number),
            u'เลขที่เช็ค': u"{}".format(receipt.cheque_number),
            u'ชื่อผู้ชำระเงิน': u"{}".format(receipt.received_from),
            u'ผู้รับเงิน/ผู้บันทึก': u"{}".format(receipt.issuer.personal_info.fullname),
            u'ตำแหน่ง': u"{}".format(receipt.issuer.personal_info.position),
            u'วันที่': u"{}".format(receipt.created_datetime.strftime('%d/%m/%Y')),
            u'หมายเหตุ': u"{}".format(receipt.comment)
            # u'GL': u"{}".format(receipt.item_gl_list if receipt and receipt.item_gl_list else ''),
            # u'Cost Center': u"{}".format(receipt.item_cost_center_list if receipt and receipt.item_cost_center_list else ''),
            # u'IO': u"{}".format(receipt.item_internal_order_list if receipt and receipt.item_internal_order_list else '')
        })
    df = DataFrame(records)
    df.to_excel('daily_payment_report.xlsx',
                header=True,
                columns=[u'เล่มที่',
                         u'เลขที่',
                         u'รายการ',
                         u'ช่องทางการชำระเงิน',
                         u'เลขที่บัตรเครดิต',
                         u'เลขที่เช็ค',
                         u'ผู้รับเงิน/ผู้บันทึก',
                         u'ตำแหน่ง',
                         u'วันที่',
                         u'หมายเหตุ',
                         # u'GL',
                         # u'Cost Center',
                         # u'IO'
                         ],
                index=False,
                encoding='utf-8')
    return send_from_directory(os.getcwd(), filename='daily_payment_report.xlsx')


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@receipt_printing.route('receipt/new/require/<int:receipt_id>', methods=['GET', 'POST'])
def require_new_receipt(receipt_id):
    form = ReceiptRequireForm()
    receipt = ElectronicReceiptDetail.query.get(receipt_id)
    if request.method == 'POST':
        filename = ''
        receipt_require = ElectronicReceiptRequest()
        form.populate_obj(receipt_require)
        receipt_require.staff = current_user
        receipt_require.detail = receipt
        drive = initialize_gdrive()
        if form.upload.data:
            if not filename or (form.upload.data.filename != filename):
                upfile = form.upload.data
                filename = secure_filename(upfile.filename)
                upfile.save(filename)
                file_drive = drive.CreateFile({'title': filename,
                                               'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
                file_drive.SetContentFile(filename)
                try:
                    file_drive.Upload()
                except:
                    flash('Failed to upload the attached file to the Google drive.', 'danger')
                else:
                    flash('The attached file has been uploaded to the Google drive', 'success')
                    receipt_require.url_drive = file_drive['id']

        db.session.add(receipt_require)
        db.session.commit()
        title = u'แจ้งเตือนคำร้องขอออกใบเสร็จใหม่ {}'.format(receipt_require.detail.number)
        message = u'เรียน คุณพิชญาสินี\n\n ขออนุมัติคำร้องขอออกใบเสร็จเลขที่ {} เล่มที่ {} เนื่องจาก {}' \
            .format(receipt_require.detail.number, receipt_require.detail.book_number, receipt_require.reason)
        message += u'\n\n======================================================'
        message += u'\nอีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ ' \
                   u'หากมีปัญหาใดๆเกี่ยวกับเว็บไซต์กรุณาติดต่อ yada.boo@mahidol.ac.th หน่วยข้อมูลและสารสนเทศ '
        message += u'\nThis email was sent by an automated system. Please do not reply.' \
                   u' If you have any problem about website, please contact the IT unit.'
        send_mail([u'pichayasini.jit@mahidol.ac.th'], title, message)
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('receipt_printing/list_to_require_receipt.html')
        # Check Error
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('receipt_printing/require_new_receipt.html', form=form, receipt=receipt)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


@receipt_printing.route('/receipt/require/list')
def list_to_require_receipt():
    return render_template('receipt_printing/list_to_require_receipt.html')


@receipt_printing.route('/api/data/require')
def get_require_receipt_data():
    query = ElectronicReceiptDetail.query.filter_by(cancelled=True)
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ElectronicReceiptDetail.number.like(u'%{}%'.format(search)),
        ElectronicReceiptDetail.book_number.like(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for r in query:
        record_data = r.to_dict()
        record_data['created_datetime'] = record_data['created_datetime'].strftime('%d/%m/%Y %H:%M:%S')
        record_data['require_receipt'] = '<a href="{}"><i class="fas fa-receipt"></i></a>'.format(
            url_for('receipt_printing.require_new_receipt', receipt_id=r.id))
        record_data['cancelled'] = '<i class="fas fa-times has-text-danger"></i>' if r.cancelled else '<i class="far fa-check-circle has-text-success"></i>'
        record_data['view_require_receipt'] = '<a href="{}"><i class="fas fa-eye"></i></a>'.format(
            url_for('receipt_printing.view_require_receipt', receipt_id=r.id))
        data.append(record_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ElectronicReceiptDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@receipt_printing.route('/receipt/require/list/view')
@login_required
@finance_head_permission.require()
def view_require_receipt():
    request_receipt = ElectronicReceiptRequest.query.all()
    return render_template('receipt_printing/view_require_receipt.html',
                           request_receipt=request_receipt)


@receipt_printing.route('/receipt-data/')
@receipt_printing.route('/receipt-data/<int:receipt_id>', methods=['GET'])
def view_receipt_by_list_type(receipt_id=None):
    list_type = request.args.get('list_type')
    if list_type == "myAccount" or list_type is None:
        record= ElectronicReceiptDetail.query.filter_by(issuer_id=current_user.id).all()
    elif list_type == "ourAccount":
        org = current_user.personal_info.org
        record = [receipt for receipt in ElectronicReceiptDetail.query.all()
                    if receipt.issuer.personal_info.org == org]
    return render_template('receipt_printing/list_all_receipts.html',
                           receipt_id=receipt_id, record=record, list_type=list_type)


@receipt_printing.route('/receipt/detail/show/<int:receipt_id>', methods=['GET', 'POST'])
def show_receipt_detail(receipt_id):
    receipt = ElectronicReceiptDetail.query.get(receipt_id)
    total = sum([t.price for t in receipt.items])
    total_thai = bahttext(total)
    return render_template('receipt_printing/receipt_detail.html',
                           receipt=receipt,
                           total=total,
                           total_thai=total_thai,
                           enumerate=enumerate)


@receipt_printing.route('/io_code_and_cost_center/select')
@finance_head_permission.require()
def select_btw_io_code_and_cost_center():
    return render_template('receipt_printing/select_io_code_and_cost_center.html', name=current_user)


@receipt_printing.route('/cost_center/show')
def show_cost_center():
    cost_center = CostCenter.query.all()
    return render_template('receipt_printing/show_cost_center.html', cost_center=cost_center)


@receipt_printing.route('/io_code/show')
def show_io_code():
    io_code = IOCode.query.all()
    return render_template('receipt_printing/show_io_code.html', io_code=io_code)


@receipt_printing.route('/cost_center/new', methods=['POST', 'GET'])
def new_cost_center():
    form = CostCenterForm()
    if form.validate_on_submit():
        cost_center_detail = CostCenter()
        cost_center_detail.id = form.cost_center.data
        db.session.add(cost_center_detail)
        db.session.commit()
        flash(u'บันทึกเรียบร้อย.', 'success')
        return redirect(url_for('receipt_printing.show_cost_center'))
    # Check Error
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('receipt_printing/new_cost_center.html', form=form, url_callback=request.referrer)


@receipt_printing.route('/io_code/new', methods=['POST', 'GET'])
def new_IOCode():
    form = IOCodeForm()
    if form.validate_on_submit():
        IOCode_detail = IOCode()
        IOCode_detail.id = form.io.data
        IOCode_detail.mission = form.mission.data
        IOCode_detail.name = form.name.data
        IOCode_detail.org = form.org.data
        db.session.add(IOCode_detail)
        db.session.commit()
        flash(u'บันทึกเรียบร้อย.', 'success')
        return redirect(url_for('receipt_printing.show_io_code'))
    # Check Error
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('receipt_printing/new_IOCode.html', form=form, url_callback=request.referrer)


@receipt_printing.route('/io_code/<string:iocode_id>/change-active-status')
def io_code_change_active_status(iocode_id):
    iocode_query = IOCode.query.filter_by(id=iocode_id).first()
    iocode_query.is_active = True if not iocode_query.is_active else False
    db.session.add(iocode_query)
    db.session.commit()
    flash(u'แก้ไขสถานะเรียบร้อยแล้ว', 'success')
    return redirect(url_for('receipt_printing.show_io_code'))