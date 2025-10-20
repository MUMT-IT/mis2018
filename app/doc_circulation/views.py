# -*- coding:utf-8 -*-
import arrow
import os
import datetime

import requests
from linebot.exceptions import LineBotApiError
from werkzeug.utils import secure_filename

from . import docbp
from flask_login import current_user, login_required
from flask import render_template, url_for, request, flash, redirect, jsonify
from pytz import timezone
from app.doc_circulation.forms import *
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from app.models import Org
from app.auth.views import line_bot_api
from linebot.models import *
from flask_mail import Message

from app.main import mail

bkk = timezone('Asia/Bangkok')

# TODO: folder ID should be stored in the Org model to organize files by organization

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

letter_header_image = '1Z1wYogBY-S1QMPfdZwnlpqHcYr_UZ0u-'
letter_header_image_for_head = '1KCkyDRa-_5Uc0aSbCFXv8hZ2MfbORT4D'


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def send_mail_head(head, round_org):
    title = u'หนังสือเวียนรอบใหม่วันที่ {} มาถึงแล้ว'.format(round_org.round)
    num_docs = len(round_org.round.documents.all())
    uri = url_for('doc.head_view_docs', round_id=round_org.round_id, _external=True)
    message = u'เรียนหัวหน้า {}\n\nหนังสือเวียนรอบใหม่มาถึงแล้วจำนวน {} ฉบับ ส่งเมื่อวันที่ {} ' \
              u'กรุณาคลิกที่ลิงค์เพื่อตรวจสอบ\n{}' \
        .format(head.personal_info.org,
                num_docs,
                round_org.round,
                uri)
    message += u'\n\nDear the head of {}\nNew {} circular letters have arrived. Circulated at {}.' \
               u'Please click the link to view the list.\n{}' \
        .format(head.personal_info.org,
                num_docs, round_org.round, uri)
    message += u'\n\n======================================================'
    message += u'\nอีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ ' \
               u'หากมีปัญหาในการเข้าถึงลิงค์กรุณาติดต่อหน่วยข้อมูลและสารสนเทศ '
    message += u'\nThis email was sent by an automated system. Please do not reply.' \
               u' If you have problem visiting the link, please contact the IT unit.'
    send_mail([u'{}@mahidol.ac.th'.format(head.email)], title, message)


def send_mail_recipient(member, round_org):
    num_docs = len(member.doc_reaches.filter_by(round_org_id=round_org.id).all())
    title = u'หนังสือเวียนรอบใหม่วันที่ {} มาถึงแล้ว'.format(round_org.round)
    uri = url_for('doc.view_round', round_id=round_org.round_id, _external=True)
    message = u'เรียน {}\n\nหนังสือเวียนรอบใหม่มาถึงแล้วจำนวน {} ฉบับ ส่งเมื่อวันที่ {} ' \
              u'กรุณาคลิกที่ลิงค์เพื่อดูรายการ\n{}' \
        .format(member.personal_info.fullname,
                num_docs,
                round_org.round,
                uri)
    message += u'\n\nDear {}\nNew {} circular letters have arrived. Circulated at {}.' \
               u'Please click the link to view the list.\n{}' \
        .format(member.personal_info.fullname,
                num_docs, round_org.round, uri)
    message += u'\n\n======================================================'
    message += u'\nอีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ ' \
               u'หากมีปัญหาในการเข้าถึงลิงค์กรุณาติดต่อหน่วยข้อมูลและสารสนเทศ '
    message += u'\nThis email was sent by an automated system. Please do not reply.' \
               u' If you have problem visiting the link, please contact the IT unit.'
    send_mail([u'{}@mahidol.ac.th'.format(member.email)], title, message)


def create_bubble_message(round_org):
    return BubbleContainer(
        hero=ImageComponent(
            layout='vertical',
            url="https://drive.google.com/uc?id={}".format(letter_header_image_for_head),
            size='full',
            aspect_mode='cover',
            aspect_ratio='20:13',
            action=URIAction(
                uri=url_for('doc.head_view_docs', round_id=round_org.round_id, _external=True),
                label='Check'
            )
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(
                    text=u'หนังสือเวียนรอบใหม่มาถึงแล้ว กรุณาตรวจสอบ',
                    wrap=True,
                    weight='bold',
                    size='xl',
                ),
                TextComponent(
                    text=u'New round of circular letters has arrived. Please approve!',
                    wrap=True,
                ),
                BoxComponent(
                    layout='baseline',
                    contents=[
                        TextComponent(
                            text='Round',
                            color='#AAAAAA',
                        ),
                        TextComponent(
                            text=str(round_org.round),
                        )
                    ]
                ),
                BoxComponent(
                    layout='baseline',
                    contents=[
                        TextComponent(
                            text='Total',
                            color='#AAAAAA',
                        ),
                        TextComponent(
                            text=str(len(round_org.round.documents.all())),
                        )
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout='vertical',
            flex=0,
            spacing='sm',
            contents=[
                ButtonComponent(
                    action=URIAction(
                        uri=url_for('doc.head_view_docs', round_id=round_org.round_id, _external=True),
                        label='Approve'
                    ),
                    height='sm'
                )
            ]
        )
    )


def create_bubble_message_recipient(round_org, member):
    num_docs = len(member.doc_reaches.filter_by(round_org_id=round_org.id).all())
    return BubbleContainer(
        hero=ImageComponent(
            layout='vertical',
            url="https://drive.google.com/uc?id={}".format(letter_header_image),
            size='full',
            aspect_mode='cover',
            aspect_ratio='20:13',
            action=URIAction(
                uri=url_for('doc.view_round', round_id=round_org.round_id, _external=True),
                label='Check'
            )
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(
                    text=u'หนังสือเวียนรอบใหม่มาถึงแล้ว',
                    wrap=True,
                    weight='bold',
                    size='xl',
                ),
                TextComponent(
                    text=u"You've got new circular letters!",
                    wrap=True,
                ),
                BoxComponent(
                    layout='baseline',
                    contents=[
                        TextComponent(
                            text='Round',
                            color='#AAAAAA',
                        ),
                        TextComponent(
                            text=str(round_org.round),
                        )
                    ]
                ),
                BoxComponent(
                    layout='baseline',
                    contents=[
                        TextComponent(
                            text='Sent at',
                            color='#AAAAAA',
                        ),
                        TextComponent(
                            text=str(arrow.get(round_org.finished_at.astimezone(bkk))
                                     .humanize()),
                        )
                    ]
                ),
                BoxComponent(
                    layout='baseline',
                    contents=[
                        TextComponent(
                            text='Total',
                            color='#AAAAAA',
                        ),
                        TextComponent(
                            text=str(num_docs),
                        )
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout='vertical',
            flex=0,
            spacing='sm',
            contents=[
                ButtonComponent(
                    action=URIAction(
                        uri=url_for('doc.view_round',
                                    round_id=round_org.round_id, _external=True),
                        label='Check'
                    ),
                    height='sm'
                )
            ]
        )
    )


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


@docbp.route('/')
@login_required
def index():
    rounds = DocRoundOrg.query.filter_by(org_id=current_user.personal_info.org.id) \
        .order_by(DocRoundOrg.sent_at.desc()).limit(60)
    starred_docs = DocDocumentReach.query.filter_by(starred=True, reacher=current_user).all()
    notes = DocDocumentReach.query.filter(DocDocumentReach.note != None).all()
    return render_template('documents/index.html',
                           rounds=rounds,
                           starred_docs=starred_docs,
                           notes=notes,
                           DocDocumentReach=DocDocumentReach)


@docbp.route('/admin/rounds/<int:round_id>/documents')
@login_required
def admin_view_round(round_id):
    round = DocRound.query.get(round_id)
    return render_template('documents/admin/docs.html', round=round)


# TODO: replace the param round_id to round_org_id as it is more straight forward.
@docbp.route('/rounds/<int:round_id>/documents')
@login_required
def view_round(round_id):
    _org = current_user.personal_info.org
    round_org = DocRoundOrg.query.filter_by(round_id=round_id, org_id=_org.id).first()
    if round_org:
        _round_reach = DocRoundOrgReach.query.filter_by(round_org_id=round_org.id, reacher=current_user).first()
        if _round_reach:
            if not _round_reach.reached_at:
                _round_reach.reached_at = datetime.datetime.now(bkk)
                db.session.add(_round_reach)
                db.session.commit()
        return render_template('documents/round.html', round_org=round_org)


@docbp.route('/api/star/<int:doc_id>')
@login_required
def api_get_star(doc_id):
    doc_reach = DocDocumentReach.query.get(doc_id)
    return jsonify({'data': doc_reach.starred})


@docbp.route('/api/star/toggle/<int:doc_id>', methods=['POST'])
@login_required
def api_toggle_star(doc_id):
    if request.method == 'POST':
        doc_reach = DocDocumentReach.query.get(doc_id)
        if doc_reach:
            if doc_reach.starred is not None:
                doc_reach.starred = not doc_reach.starred
            else:
                doc_reach.starred = True
            db.session.add(doc_reach)
            db.session.commit()
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'failed'}), 404


@docbp.route('/starred-documents/<int:doc_reach_id>')
@login_required
def view_starred_doc(doc_reach_id):
    _org = current_user.personal_info.org
    doc_reach = DocDocumentReach.query.get(doc_reach_id)
    return render_template('documents/starred_doc.html', doc_reach=doc_reach)


@docbp.route('/api/has-read-yet/<int:doc_reach_id>')
@login_required
def api_has_read_yet(doc_reach_id):
    doc_reach = DocDocumentReach.query.get(doc_reach_id)
    if doc_reach:
        return jsonify({
            'data': True if doc_reach.reached_at is not None else False,
            'readAt': doc_reach.reached_at.isoformat() if doc_reach.reached_at else None
        })
    return jsonify({'data': 'failed'}), 404


@docbp.route('/api/mark-as-read/<int:doc_reach_id>', methods=['POST'])
@login_required
def api_mark_as_read(doc_reach_id):
    doc_reach = DocDocumentReach.query.get(doc_reach_id)
    if doc_reach:
        if doc_reach.reached_at is None:
            doc_reach.reached_at = datetime.datetime.now(bkk)
            db.session.add(doc_reach)
            db.session.commit()
        return jsonify({'data': True, 'readAt': doc_reach.reached_at.isoformat() if doc_reach.reached_at else None})
    else:
        return jsonify({'data': 'failed'}), 404


@docbp.route('/api/note-to-self/<int:doc_reach_id>', methods=['POST'])
@login_required
def api_note_to_self(doc_reach_id):
    doc_reach = DocDocumentReach.query.get(doc_reach_id)
    data = request.get_json()
    if doc_reach:
        if doc_reach.note is None:
            doc_reach.note = data['note']
            db.session.add(doc_reach)
            db.session.commit()
        return jsonify({'data': 'success'})
    else:
        return jsonify({'data': 'failed'}), 404


@docbp.route('/api/has-note/<int:doc_reach_id>')
@login_required
def api_has_note(doc_reach_id):
    doc_reach = DocDocumentReach.query.get(doc_reach_id)
    if doc_reach:
        return jsonify({'data': True if doc_reach.note is not None else False,
                        'note': doc_reach.note})
    return jsonify({'data': 'failed'}), 404


@docbp.route('/rounds/mark-as-read/<int:doc_reach_id>', methods=['POST'])
@login_required
def mark_as_read(doc_reach_id):
    star_view = request.args.get('star_view', 'false')
    doc_reach = DocDocumentReach.query.get(doc_reach_id)
    if doc_reach:
        doc_reach.reached_at = datetime.datetime.now(bkk)
        db.session.add(doc_reach)
        db.session.commit()
        if star_view == 'true':
            return redirect(url_for('doc.view_starred_doc', doc_reach_id=doc_reach_id))
        else:
            return redirect(url_for('doc.view_round', round_id=doc_reach.round_org.round.id))
    else:
        return 'Record not found.'


@docbp.route('/rounds/starred/<int:doc_reach_id>')
@login_required
def star(doc_reach_id):
    star_view = request.args.get('star_view', 'false')
    doc_reach = DocDocumentReach.query.get(doc_reach_id)
    if doc_reach:
        if doc_reach.starred is not True:
            doc_reach.starred = True
        else:
            doc_reach.starred = False
        db.session.add(doc_reach)
        db.session.commit()
        if star_view == 'true':
            return redirect(url_for('doc.view_starred_doc', doc_reach_id=doc_reach_id))
        else:
            return redirect(url_for('doc.view_round', round_id=doc_reach.round_org.round.id))
    else:
        return 'Record not found.'


@docbp.route('/documents/<int:rec_id>')
@login_required
def view_recv_record(rec_id):
    rec = DocReceiveRecord.query.get(rec_id)
    return render_template('documents/recv_record.html', rec=rec)


@docbp.route('/admin')
@login_required
def admin_index():
    rounds = DocRound.query.order_by(DocRound.date.desc()) \
        .order_by(DocRound.created_at.desc()).limit(60)
    return render_template('documents/admin/index.html', rounds=rounds)


@docbp.route('/admin/rounds', methods=['GET', 'POST'])
@login_required
def add_round():
    form = RoundForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_round = DocRound()
            form.populate_obj(new_round)
            new_round.created_at = datetime.datetime.now(bkk)
            new_round.creator = current_user
            db.session.add(new_round)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('doc.admin_index'))
        else:
            for err in form.errors:
                flash('{}'.format(err), 'danger')
    return render_template('documents/admin/round_form.html', form=form)


@docbp.route('/admin/rounds/<int:round_id>/docs/<int:doc_id>', methods=['GET', 'POST'])
@docbp.route('/admin/rounds/<int:round_id>/docs', methods=['GET', 'POST'])
@login_required
def add_document(round_id, doc_id=None):
    if doc_id:
        doc = DocDocument.query.get(doc_id)
        form = DocumentForm(obj=doc)
    else:
        form = DocumentForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            if not doc_id:
                new_doc = DocDocument()
                new_doc.stage = 'drafting'
                filename = ''
                fileurl = ''
            else:
                new_doc = doc
                filename = doc.file_name
                fileurl = doc.url
            form.populate_obj(new_doc)
            new_doc.round_id = round_id
            if not new_doc.addedAt:
                new_doc.addedAt = datetime.datetime.now(bkk)
            if new_doc.deadline:
                new_doc.deadline = bkk.localize(new_doc.deadline)
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
                        permission = file_drive.InsertPermission({'type': 'anyone',
                                                                  'value': 'anyone',
                                                                  'role': 'reader'})
                    except:
                        flash('Failed to upload the attached file to the Google drive.', 'danger')
                    else:
                        flash('The attached file has been uploaded to the Google drive', 'success')
                        new_doc.url = file_drive['id']
                        new_doc.file_name = filename
            else:
                new_doc.file_name = filename
                new_doc.url = fileurl
            db.session.add(new_doc)
            db.session.commit()
            if doc_id:
                flash('The document has been updated.', 'success')
            else:
                flash('New document has been added.', 'success')
            return redirect(url_for('doc.admin_view_round', round_id=round_id))
        else:
            for field, err in form.errors.items():
                flash('{} {}'.format(field, err), 'danger')
    return render_template('documents/admin/document_form.html', form=form, round_id=round_id)


@docbp.route('/admin/docs/<int:doc_id>/send', methods=['GET', 'POST'])
@login_required
def send_document(doc_id):
    doc = DocDocument.query.get(doc_id)
    if doc:
        doc.stage = 'ready'
        db.session.add(doc)
        db.session.commit()
        flash('The document is ready to be reviewed.', 'success')
        return redirect(url_for('doc.admin_view_round', round_id=doc.round_id))
    else:
        flash('The document has been not been found.', 'danger')
        return redirect(url_for('doc.admin_index'))


@docbp.route('/admin/rounds/<int:round_id>/send_for_review', methods=['GET', 'POST'])
@login_required
def send_round_for_review(round_id):
    form = RoundSendForm()
    select_orgs = (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 27, 28, 29, 30, 31)
    form.targets.choices = [(org.id, org.name) for org in Org.query.all() if org.id in select_orgs]
    n_dept = 0
    if request.method == 'POST':
        if form.validate_on_submit():
            for target_id in form.targets.data:
                _record = DocRoundOrg.query.filter_by(org_id=target_id, round_id=round_id).first()
                if not _record:
                    send_record = DocRoundOrg(
                        org_id=target_id,
                        round_id=round_id,
                        sent_at=datetime.datetime.now(bkk)
                    )
                    n_dept += 1
                    db.session.add(send_record)
                    _org = Org.query.get(target_id)
                    _head_org = StaffAccount.query.filter_by(email=_org.head).first()
                    if _head_org:
                        try:
                            line_bot_api.push_message(to=_head_org.line_id,
                                                      messages=FlexSendMessage(
                                                          alt_text='Circular Letters',
                                                          contents=create_bubble_message(send_record)
                                                      ))
                        except LineBotApiError:
                            flash('ไม่สามารถส่งข้อความเตือนในระบบไลน์ได้เนื่องจากระบบขัดข้อง', 'warning')
                        send_mail_head(_head_org, send_record)
                else:
                    _org = Org.query.get(target_id)
                    flash(u'Documents were sent to {} about {}.'
                          .format(_org.name, arrow.get(_record.sent_at.astimezone(bkk)).humanize()), 'warning')
            if n_dept > 0:
                db.session.commit()
                flash('The documents have been sent to selected departments for a review.', 'success')
            return redirect(url_for('doc.admin_index'))
        else:
            for field, error in form.errors:
                flash('{} {}'.format(field, error), 'danger')

    form.targets.data = [current_user.personal_info.org.id]

    return render_template('documents/admin/send_for_review.html', form=form, round_id=round_id)


@docbp.route('/head/rounds/<int:round_id>/documents')
@login_required
def head_view_docs(round_id):
    _org = current_user.personal_info.org
    if _org.head == current_user.email:
        sent_round = DocRoundOrg.query.filter_by(org_id=_org.id, round_id=round_id).first()
        return render_template('documents/head/docs.html', sent_round=sent_round)
    return u'You do have a permission to review documents targeted for this {}.'.format(_org.name)


@docbp.route('/head/rounds')
@login_required
def head_view_rounds():
    _org = current_user.personal_info.org
    if _org.head == current_user.email:
        sent_rounds = DocRoundOrg.query.filter_by(org_id=_org.id) \
            .order_by(DocRoundOrg.sent_at.desc()).limit(60)
        return render_template('documents/head/rounds.html', sent_rounds=sent_rounds)
    else:
        return 'You are not a head of the department', 403


@docbp.route('/head/sent_rounds/<int:sent_round_org_id>/docs/<int:doc_id>/review', methods=['GET', 'POST'])
@login_required
def head_review(doc_id, sent_round_org_id):
    doc = DocDocument.query.get(doc_id)
    if current_user.email == current_user.personal_info.org.head:
        _DocumentReceiptForm = create_doc_receipt_form(current_user.personal_info.org)
        form = _DocumentReceiptForm()
        if request.method == 'POST':
            if form.validate_on_submit():
                receipt = DocReceiveRecord()
                form.populate_obj(receipt)
                receipt.round_org_id = sent_round_org_id
                receipt.doc = doc
                receipt.sender = current_user
                receipt.sent_at = datetime.datetime.now(bkk)
                db.session.add(receipt)
                for member in receipt.members:
                    _round_reach = DocRoundOrgReach(
                        reacher=member.staff_account,
                        round_org_id=sent_round_org_id,
                        created_at=datetime.datetime.now(bkk),
                    )
                    _doc_reach = DocDocumentReach(
                        reacher=member.staff_account,
                        created_at=datetime.datetime.now(bkk),
                        doc_id=doc.id,
                        round_org_id=sent_round_org_id,
                    )
                    db.session.add(_doc_reach)
                    db.session.add(_round_reach)
                db.session.commit()
                flash('The document has been sent to the members.', 'success')
                return redirect(url_for('doc.head_view_docs', round_id=doc.round_id))
            else:
                for field, err in form.errors.items():
                    flash('{} {}'.format(field, err), 'danger')
        return render_template('documents/head/review.html', form=form, doc=doc)


@docbp.route('/head/sent_rounds/<int:sent_round_org_id>')
@login_required
def head_finish_round(sent_round_org_id):
    """
    Send documents to all selected members.

    :param sent_round_org_id: an ID of a record of an organizational round
    """
    round_org = DocRoundOrg.query.get(sent_round_org_id)
    sent_records = DocReceiveRecord.query.filter_by(round_org_id=round_org.id).all()
    if round_org:
        round_org.finished_at = datetime.datetime.now(bkk)
        db.session.add(round_org)
        db.session.commit()
    members = set()
    for record in sent_records:
        members.update(record.members)
    for member in members:
        line_id = member.staff_account.line_id
        if os.environ['FLASK_ENV'] == 'production':
            if line_id:
                try:
                    bubble_message = create_bubble_message_recipient(round_org, member.staff_account)
                    line_bot_api.push_message(to=line_id,
                                              messages=FlexSendMessage(alt_text='New circular letters',
                                                                   contents=bubble_message))
                except LineBotApiError:
                    flash('ไม่สามารถส่งข้อความเตือนในระบบไลน์ได้เนื่องจากระบบขัดข้อง', 'warning')

            send_mail_recipient(member.staff_account, round_org)

    return redirect(url_for('doc.head_view_rounds'))


@docbp.route('/head/documents/<int:doc_id>/sent_round_org/<int:sent_round_org_id>/receipt')
@login_required
def head_view_send_receipt(doc_id, sent_round_org_id):
    receipt = DocReceiveRecord.query.filter_by(doc_id=doc_id, round_org_id=sent_round_org_id).first()
    if receipt:
        return render_template('documents/head/sent_records.html', receipt=receipt)
    else:
        flash(u'No recipients for this round. กรุณาระบุผู้รับ', 'danger')
        round_org = DocRoundOrg.query.get(sent_round_org_id)
    return redirect(url_for('doc.head_view_docs', round_id=round_org.round_id))


@docbp.route('/head/receipts/<int:receipt_id>/members/<int:member_id>', methods=['GET', 'POST'])
@login_required
def head_add_private_msg(receipt_id, member_id):
    receipt = DocReceiveRecord.query.get(receipt_id)
    doc_reach = DocDocumentReach.query.filter_by(
        doc_id=receipt.doc_id,
        reacher_id=member_id,
        round_org_id=receipt.round_org_id
    ).first()
    if doc_reach:
        form = PrivateMessageForm(obj=doc_reach)
    else:
        form = PrivateMessageForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(doc_reach)
            db.session.add(doc_reach)
            db.session.commit()
            flash('Your message has been sent.', 'success')
            return redirect(url_for('doc.head_view_send_receipt',
                                    doc_id=receipt.doc_id,
                                    sent_round_org_id=receipt.round_org_id))
    return render_template('documents/head/private_message_form.html',
                           form=form, doc_reach=doc_reach)


@docbp.route('/head/receipts/<int:receipt_id>/members/<int:member_id>/cancel', methods=['GET', 'POST'])
@login_required
def head_cancel_sending(receipt_id, member_id):
    member = StaffPersonalInfo.query.get(member_id)
    receipt = DocReceiveRecord.query.get(receipt_id)
    receipt.members.remove(member)
    db.session.add(receipt)
    doc_reach = DocDocumentReach.query.filter_by(doc_id=receipt.doc_id,
                                                 reacher_id=member_id,
                                                 round_org_id=receipt.round_org_id).first()

    if doc_reach:
        db.session.delete(doc_reach)

    round_reach = DocRoundOrgReach.query.filter_by(reacher_id=member_id,
                                                   round_org_id=receipt.round_org_id).first()
    if round_reach:
        db.session.delete(round_reach)

    db.session.commit()
    return render_template('documents/head/sent_records.html', receipt=receipt)
