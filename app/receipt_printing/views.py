# -*- coding:utf-8 -*-
from datetime import datetime

import pytz
from bahttext import bahttext
from flask import render_template, request, flash, redirect, url_for, send_file
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
from ..main import db

bangkok = pytz.timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = ['xlsx', 'xls']


@receipt_printing.route('/index')
def index():
    return render_template('receipt_printing/index.html')


@receipt_printing.route('/landing')
def landing():
    return render_template('receipt_printing/landing.html')


@receipt_printing.route('/receipt/create', methods=['POST', 'GET'])
def create_receipt():
    receipt_detail = ElectronicReceiptDetail.query.first()
    form = ReceiptDetailForm(obj=receipt_detail)
    cashiers = ElectronicReceiptCashier.query.all()

    if form.validate_on_submit():
        receipt_detail.created_datetime = datetime.now(tz=bangkok)
        form.populate_obj(receipt_detail)
        db.session.add(receipt_detail)
        db.session.commit()
        flash(u'บันทึกการสร้างใบเสร็จรับเงินสำเร็จ.', 'success')
        return redirect(url_for('receipt_printing.list_all_receipts'))
    # Check Error
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('receipt_printing/new_receipt.html', form=form, cashiers=cashiers)


@receipt_printing.route('/list/all', methods=['GET'])
def list_all_receipts():
    record = ElectronicReceiptDetail.query.all()
    return render_template('receipt_printing/list_all_receipts.html', record=record)


sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))



@receipt_printing.route('/receipts/pdf/blank')
def export_blank_receipt_pdf():
    # logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

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
    book_id = 'MTG000000'
    receipt_number = 0
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
    ได้รับเงินจาก / RECEIVED FROM {customer_name}
    </font></para>
    '''.format(customer_name='-')

    customer = Table([[Paragraph(customer_name, style=style_sheet['ThaiStyle']),
                    ]],
                     colWidths=[300, 200]
                     )
    customer.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                  ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    items = [[Paragraph('<font size=10>ลำดับ / No.</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รายการ / Description</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รวม / Total</font>', style=style_sheet['ThaiStyleCenter']),
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
    total_text = "รวมเงินทั้งสิ้น {}".format(total_thai.encode('utf-8'))
    items.append([
        Paragraph('<font size=12>{}</font>'.format(total_text), style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(total), style=style_sheet['ThaiStyleNumber'])
    ])
    item_table = Table(items, colWidths=[40, 240, 70, 70, 70])
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

    payment_info = Paragraph('<font size=14>ชำระเงินด้วย / PAYMENT METHOD เงินสด / CASH</font>', style=style_sheet['ThaiStyle'])

    total_content = [[payment_info,
                      Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
                      Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]

    total_table = Table(total_content, colWidths=[300, 150, 50])

    notice_text = '''<para align=center><font size=10>
    ใบเสร็จฉบับนี้จะสมบูรณ์เมื่อมีลายมือชื่อผู้รับเงินเท่านั้น / The receipt is not completed without the cashier's signature.
    <br/>*สิทธิการเบิกตามระเบียบกระทรวงการคลัง / Reimbursement is in accordance with the regulation of the Ministry of Finance.</font></para>
    '''
    notice = Table([[Paragraph(notice_text, style=style_sheet['ThaiStyle'])]])

    sign_text = '''<para align=center><font size=12>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbspลงชื่อ ............................................ ผู้รับเงิน / Cashier<br/>
    ({})<br/>
    ตำแหน่ง / Position {}
    </font></para>'''.format('-', '-')

    if request.args.get('receipt_copy') == 'copy':
        data.append(header_copy)
    else:
        data.append(header_ori)

    data.append(Paragraph('<para align=center><font size=18>ใบเสร็จรับเงิน / RECEIPT<br/><br/></font></para>',
                          style=style_sheet['ThaiStyle']))
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