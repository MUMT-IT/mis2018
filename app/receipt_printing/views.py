# -*- coding:utf-8 -*-
import os
from datetime import datetime

import pytz
from bahttext import bahttext
from flask import render_template, request, flash, redirect, url_for, send_file, send_from_directory
from pandas import DataFrame
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, TableStyle, Table, Spacer, PageBreak

from . import receipt_printing_bp as receipt_printing
from .forms import *
from .models import *
from ..comhealth.models import ComHealthReceiptID
from ..main import db
from ..roles import finance_permission

bangkok = pytz.timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = ['xlsx', 'xls']


@receipt_printing.route('/index')
@finance_permission.require()
def index():
    return render_template('receipt_printing/index.html')


@receipt_printing.route('/landing')
def landing():
    return render_template('receipt_printing/landing.html')


@receipt_printing.route('/receipt/create', methods=['POST', 'GET'])
def create_receipt():
    action = request.args.get('action')
    form = ReceiptDetailForm()
    cashiers = ElectronicReceiptCashier.query.all()
    receipt_book = ComHealthReceiptID.query.filter_by(code='MTG').first()

    if form.validate_on_submit():
        if action == 'add-items':
            form.items.append_entry()
            return render_template('receipt_printing/new_receipt.html', form=form, cashiers=cashiers)
        total_price = 0
        for price in form.price:
            total_price += price

        receipt_detail = ElectronicReceiptDetail()
        receipt_detail.paid_amount = total_price
        # receipt_detail.created_datetime = datetime.now(tz=bangkok)
        form.populate_obj(receipt_detail)  #insert data from Form to Model
        receipt_detail.number = receipt_book.next
        receipt_book.count += 1
        receipt_detail.book_number = receipt_book.book_number
        db.session.add(receipt_detail)
        db.session.commit()
        flash(u'บันทึกการสร้างใบเสร็จรับเงินสำเร็จ.', 'success')
        return redirect(url_for('receipt_printing.list_all_receipts'))
    # Check Error
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('receipt_printing/new_receipt.html', form=form, cashiers=cashiers)


@receipt_printing.route('/receipt/create/add-items', methods=['POST', 'GET'])
def list_add_items():
    form = ReceiptDetailForm()
    form.items.append_entry()
    item_form = form.items[-1]
    return u'''
    <div class="field">
        <label class="label">{}</label>
        <div class="control">
            {}
        </div>
    </div>
    <div class="field">
        <label class="label">{}</label>
        <div class="control">
            {}
        </div>
    </div>
    <div class="field">
        <label class="label">{}</label>
        <div class="control">
            {}
        </div>
    </div>
    '''.format(item_form.item.label, item_form.item(class_="input"), item_form.price.label, item_form.price(class_="input", placeholder=u"฿"),
               item_form.comment.label, item_form.comment(class_="input"))


@receipt_printing.route('/receipt/create/items-delete', methods=['POST', 'GET'])
def delete_items():
    form = ReceiptDetailForm()
    form.items.append_entry()
    item_form = form.items[-1]
    for item in item_form:
        print(item)
    form.items.pop_entry()
    return '''
    '''


@receipt_printing.route('/list/receipts', methods=['GET'])
def list_all_receipts():
    record = ElectronicReceiptDetail.query.all()
    return render_template('receipt_printing/list_all_receipts.html', record=record)


sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))


@receipt_printing.route('/receipts/pdf/<int:receipt_id>')
def export_receipt_pdf(receipt_id):
    receipt = ElectronicReceiptDetail.query.get(receipt_id)

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
    <font size=12>
    เล่มที่ / Book No. {book_id}<br/>
    เลขที่ / No. {receipt_number}<br/>
    วันที่ / Date {issued_date}
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
    price = 0
    item = [Paragraph('<font size=12>{} ({})</font>'.format('-', '-'), style=style_sheet['ThaiStyle'])]
    item.append(
        Paragraph('<font size=12>{:,.2f}</font>'.format(price), style=style_sheet['ThaiStyleNumber']))
    item.append(Paragraph('<font size=12>-</font>', style=style_sheet['ThaiStyleCenter']))
    item.append(
        Paragraph('<font size=12>{:,.2f}</font>'.format(price), style=style_sheet['ThaiStyleNumber']))
    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(total), style=style_sheet['ThaiStyleNumber'])
    ])

    n = len(items)
    while n <=25:
        items.append([
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
        ])
        n += 1

    total_thai = bahttext(total)
    total_text = "รวมเงินทั้งสิ้น/ TOTAL {}".format(total_thai.encode('utf-8'))
    items.append([
        Paragraph('<font size=12>{}</font>'.format(total_text), style=style_sheet['ThaiStyle']),
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

    total_table = Table(total_content, colWidths=[300, 150, 50])

    notice_text = '''<para align=center><font size=10>
    กรณีชำระด้วยเช็ค ใบเสร็จรับเงินฉบับนี้จะสมบูรณ์ต่อเมื่อ เรียกเก็บเงินได้ตามเช็คเรียบร้อยแล้ว <br/> If paying by cheque, a receipt will be completed upon receipt of the cheque complete.
    <br/>เอกสารนี้พิมพ์จากคอมพิวเตอร์</font></para>
    '''
    notice = Table([[Paragraph(notice_text, style=style_sheet['ThaiStyle'])]])

    sign_text = '''<para align=center><font size=12>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbspลงชื่อ ............................................ ผู้รับเงิน / Cashier<br/>
    ({})<br/>
    ตำแหน่ง / Position {}
    </font></para>'''.format(receipt.issuer.staff.personal_info.fullname.encode('utf-8'),
                             receipt.issuer.position.encode('utf-8'))

    if request.args.get('receipt_copy') == 'copy':
        data.append(header_copy)
    else:
        data.append(header_ori)

    # data.append(Paragraph('<para align=center><font size=18>ใบเสร็จรับเงิน / RECEIPT<br/><br/></font></para>',
    #                       style=style_sheet['ThaiStyle']))
    data.append(customer)
    data.append(Spacer(1, 12))
    data.append(Spacer(1, 6))
    data.append(item_table)
    data.append(Spacer(1, 6))
    data.append(total_table)
    data.append(Spacer(1, 6))
    data.append(Spacer(1, 12))
    data.append(Paragraph(sign_text, style=style_sheet['ThaiStyle']))
    data.append(Spacer(1, 6))
    data.append(notice)
    data.append(PageBreak())
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)

    return send_file('receipt.pdf')


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
    return redirect(url_for('receipt_printing.list_all_receipts'))


@receipt_printing.route('/daily/payment/report')
def daily_payment_report():
    record = ElectronicReceiptDetail.query.all()
    return render_template('receipt_printing/daily_payment_report.html', record=record)


@receipt_printing.route('/daily/payment/report/download')
def download_daily_payment_report():
    records = []
    receipt_record = ElectronicReceiptDetail.query.all()

    for receipt in receipt_record:
        records.append({
            u'เล่มที่': u"{}".format(receipt.book_number),
            u'เลขที่': u"{}".format(receipt.number),
            u'ช่องทางการชำระเงิน': u"{}".format(receipt.payment_method),
            u'เลขที่บัตรเครดิต': u"{}".format(receipt.card_number),
            u'เลขที่เช็ค': u"{}".format(receipt.cheque_number),
            u'ชื่อผู้ชำระเงิน': u"{}".format(receipt.received_from),
            u'ผู้รับเงิน/ผู้บันทึก': u"{}".format(receipt.cashier),
            u'ตำแหน่ง': u"{}".format(receipt.issuer.staff.personal_info.fullname),
            u'หมายเหตุ': u"{}".format(receipt.comment),
        })
    df = DataFrame(records)
    df.to_excel('daily_payment_report.xlsx',
                header=True,
                columns=[u'เล่มที่',
                         u'เลขที่',
                         u'ช่องทางการชำระเงิน',
                         u'เลขที่บัตรเครดิต',
                         u'เลขที่เช็ค',
                         u'ผู้รับเงิน/ผู้บันทึก',
                         u'ตำแหน่ง',
                         u'หมายเหตุ'
                         ],
                index=False,
                encoding='utf-8')
    return send_from_directory(os.getcwd(), filename='daily_payment_report.xlsx')