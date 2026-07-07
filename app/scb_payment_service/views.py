import datetime
import arrow
import os

import requests
from flask import jsonify, request, render_template, url_for, current_app
from flask_jwt_extended import (create_access_token, get_jwt_identity, jwt_required, get_current_user,
                                create_refresh_token)
from werkzeug.security import check_password_hash

from . import scb_payment
from .models import ScbPaymentServiceApiClientAccount, ScbPaymentRecord
from ..main import csrf, db
import uuid
from flask_mail import Message
from ..main import mail

AUTH_URL = os.environ.get('SCB_AUTH_URL')
QRCODE_URL = os.environ.get('SCB_QRCODE_URL')
APP_KEY = os.environ.get('SCB_APP_KEY')
APP_SECRET = os.environ.get('SCB_APP_SECRET')
BILLERID = os.environ.get('BILLERID')
REF3 = os.environ.get('SCB_REF3')
QR30_INQUIRY = os.environ.get('QR30_INQUIRY')
SLIP_VERIFICATION = os.environ.get('SLIP_VERIFICATION')


def get_fixie_proxies():
    fixie_host = os.environ.get("FIXIE_SOCKS_HOST")
    if not fixie_host:
        return None
    proxy_url = f"socks5h://{fixie_host}"
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def _log_scb_proxy_status(action):
    current_app.logger.info(
        "SCB request %s using Fixie proxy: %s",
        action,
        "enabled" if get_fixie_proxies() else "disabled"
    )


def _log_cloudfront_block(resp):
    if resp is None:
        return
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if resp.status_code == 403 and "html" in content_type:
        current_app.logger.error(
            "SCB request blocked by CloudFront/WAF. Check Fixie proxy and SCB allowlist."
        )


def scb_qr30_inquiry(reference1, transaction_date, event_code='00300100'):
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'requestUId': str(uuid.uuid4()),
        'resourceOwnerId': APP_KEY
    }
    proxies = get_fixie_proxies()
    _log_scb_proxy_status('qr30-inquiry-auth')
    response = requests.post(AUTH_URL, headers=headers, json={
        'applicationKey': APP_KEY,
        'applicationSecret': APP_SECRET
    }, proxies=proxies, timeout=30)
    _log_cloudfront_block(response)
    response.raise_for_status()
    access_token = response.json().get('data', {}).get('accessToken')
    if not access_token:
        return {}
    headers['authorization'] = 'Bearer {}'.format(access_token)
    _log_scb_proxy_status('qr30-inquiry')
    resp = requests.get(
        QR30_INQUIRY,
        params={
            "billerId": BILLERID,
            "reference1": reference1,
            "transactionDate": transaction_date,
            "eventCode": event_code
        },
        headers=headers,
        proxies=proxies,
        timeout=30
    )
    _log_cloudfront_block(resp)
    return resp.json()


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def generate_qrcode(amount, ref1, ref2, ref3, expired_at=None):
    if not expired_at:
        expired_at = arrow.now('Asia/Bangkok').shift(weeks=24).format('YYYY-MM-DD 00:00:00')
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'requestUId': str(uuid.uuid4()),
        'resourceOwnerId': APP_KEY
    }
    response = None
    try:
        proxies = get_fixie_proxies()
        _log_scb_proxy_status('auth')
        response = requests.post(AUTH_URL, headers=headers, json={
            'applicationKey': APP_KEY,
            'applicationSecret': APP_SECRET
        }, proxies=proxies, timeout=30)
        _log_cloudfront_block(response)
        response.raise_for_status()
        response_data = response.json()
        access_token = response_data['data']['accessToken']
    except requests.RequestException as exc:
        current_app.logger.exception(
            'SCB QR auth request failed for ref1=%s ref2=%s amount=%s status=%s body=%s',
            ref1,
            ref2,
            amount,
            getattr(response, 'status_code', None),
            (response.text[:1000] if response is not None and getattr(response, 'text', None) else None)
        )
        return {
            'message': 'Failed to authenticate with SCB before generating QR code.',
            'details': str(exc)
        }
    except (KeyError, TypeError, ValueError) as exc:
        current_app.logger.exception(
            'SCB QR auth response malformed for ref1=%s ref2=%s amount=%s status=%s body=%s',
            ref1,
            ref2,
            amount,
            getattr(response, 'status_code', None),
            (response.text[:1000] if response is not None and getattr(response, 'text', None) else None)
        )
        return {
            'message': 'SCB authentication returned an unexpected response.',
            'details': str(exc)
        }

    headers['authorization'] = 'Bearer {}'.format(access_token)

    try:
        proxies = get_fixie_proxies()
        _log_scb_proxy_status('qrcode-create')
        qrcode_resp = requests.post(QRCODE_URL, headers=headers, json={
            'qrType': 'PP',
            'amount': '{}'.format(amount),
            'ppType': 'BILLERID',
            'ppId': BILLERID,
            'ref1': ref1,
            'ref2': ref2,
            'ref3': ref3,
            'expiryDate': expired_at,
            'numberOfTimes': 1
        }, proxies=proxies, timeout=30)
        _log_cloudfront_block(qrcode_resp)
    except requests.RequestException as exc:
        current_app.logger.exception(
            'SCB QR code request failed for ref1=%s ref2=%s amount=%s',
            ref1, ref2, amount
        )
        return {
            'message': 'Failed to request QR code from SCB.',
            'details': str(exc)
        }
    if qrcode_resp.status_code == 200:
        try:
            qr_image = qrcode_resp.json()['data']['qrImage']
            return {'qrImage': qr_image}
        except (KeyError, TypeError, ValueError) as exc:
            current_app.logger.exception(
                'SCB QR code response malformed for ref1=%s ref2=%s amount=%s',
                ref1, ref2, amount
            )
            return {
                'message': 'SCB QR code response was malformed.',
                'details': str(exc)
            }
    else:
        current_app.logger.error(
            'SCB QR code request returned status=%s for ref1=%s ref2=%s amount=%s body=%s',
            qrcode_resp.status_code,
            ref1,
            ref2,
            amount,
            qrcode_resp.text[:1000]
        )
        try:
            return qrcode_resp.json()
        except ValueError:
            return {
                'message': 'SCB QR code request failed with a non-JSON response.',
                'status_code': qrcode_resp.status_code
            }


@scb_payment.route('/api/v1.0/login', methods=['POST'])
@csrf.exempt
def login():
    client_id = request.get_json().get('client_id')
    client_secret = request.get_json().get('client_secret')
    client = ScbPaymentServiceApiClientAccount.query.get(client_id)
    if client:
        if check_password_hash(client._secret_hash, client_secret):
            return jsonify(access_token=create_access_token(identity=client_id),
                           refresh_token=create_refresh_token(identity=client_id))
        else:
            return jsonify({'message': 'Invalid client secret.'}), 403
    else:
        return jsonify({'message': 'Client account not found.'}), 404


@scb_payment.route('/api/v1.0/refresh', methods=['POST'])
@jwt_required(refresh=True)
@csrf.exempt
def refresh():
    current_user = get_jwt_identity()
    ret = {
        'access_token': create_access_token(identity=current_user)
    }
    return jsonify(ret), 200


@scb_payment.route('/api/v1.0/qrcode/create', methods=['POST'])
@jwt_required()
@csrf.exempt
def create_qrcode():
    # TODO: set expiration time to 60 minutes.
    amount = request.get_json().get('amount')
    ref1 = request.get_json().get('ref1')
    ref2 = request.get_json().get('ref2')
    customer1 = request.get_json().get('customer1')
    customer2 = request.get_json().get('customer2')
    service = request.get_json().get('service')
    expire_datetime = request.get_json().get('expire_datetime')
    record = ScbPaymentRecord.query.filter_by(bill_payment_ref1=ref1, bill_payment_ref2=ref2).first()
    if amount is None:
        return jsonify({'message': 'Amount is needed'}), 400
    data = generate_qrcode(amount, ref1=ref1, ref2=ref2, ref3=REF3, expired_at=expire_datetime)
    if 'qrImage' in data:
        if not record:
            record = ScbPaymentRecord(bill_payment_ref1=ref1, bill_payment_ref2=ref2,
                                      service=service,
                                      customer1=customer1, customer2=customer2,
                                      amount=amount)
        else:
            record.amount = amount
        db.session.add(record)
        db.session.commit()
        return jsonify({'data': data})
    else:
        return jsonify({'error': data}), 500


@scb_payment.route('/api/v1.0/payment-confirm', methods=['GET', 'POST'])
@csrf.exempt
def confirm_payment():
    data = request.get_json()
    record = ScbPaymentRecord.query.filter_by(bill_payment_ref1=data['billPaymentRef1'],
                                              bill_payment_ref2=data['billPaymentRef2']).first()
    record.assign_data_from_request(data)
    db.session.add(record)
    db.session.commit()

    # If this QR belongs to Continuing Education, mark the RegisterPayment as paid.
    #TODO: send a request to update the payment status instead.
    try:
        import re
        ref2 = str(data.get('billPaymentRef2') or '')
        m = re.search(r'^RP(\d+)$', ref2)
        if m:
            payment_id = int(m.group(1))
            from app.continuing_edu.models import CERegisterPayment, CERegisterPaymentStatus
            pay = CERegisterPayment.query.get(payment_id)
            if pay and not pay.transaction_id:
                pay.transaction_id = data.get('transactionId')
            paid_status = CERegisterPaymentStatus.query.filter(
                (CERegisterPaymentStatus.register_payment_status_code == 'paid') |
                (CERegisterPaymentStatus.name_en == 'paid')
            ).first()
            if pay and paid_status:
                pay.payment_status_id = paid_status.id
                pay.payment_date = datetime.datetime.now()
                db.session.add(pay)
                db.session.commit()
    except Exception as e:
        print(f"[SCB_CONFIRM_PAYMENT] Failed to mark RegisterPayment paid: {e}")
    title = 'แจ้งเตือน QR Payment บริการอัตโนมัติแจ้งเตือนการทำธุรกรรมของคุณ {}'.format(record.payer_name)
    message = 'เรียน คุณพิชญาสินี\n\n แจ้งเตือนชื่อผู้จ่าย {} ผู้รับ {} จำนวน {} ref1: {} ref2: {} transaction id: {}' \
        .format(record.payer_name, record.payee_name, record.amount, record.bill_payment_ref1, record.bill_payment_ref2, record.transaction_id)
    message += '\n\n======================================================'
    message += '\nอีเมลฉบับนี้เป็นการแจ้งข้อมูลจากระบบอัตโนมัติ กรุณาอย่าตอบกลับ ' \
               'หากมีข้อสงสัยหรือต้องการสอบถามรายละเอียดเพิ่มเติม ปัญหาใดๆเกี่ยวกับเว็บไซต์กรุณาติดต่อ yada.boo@mahidol.ac.th หน่วยข้อมูลและสารสนเทศ '
    message += '\nThis email was sent by an automated system. Please do not reply.' \
               ' If you have any problem about website, please contact the IT unit.'
    send_mail(['pichayasini.jit@mahidol.ac.th'], title, message)
    print(data)
    return jsonify({
        'resCode': '00',
        'recDesc': 'success',
        'transactionId': data['transactionId']
    })


@scb_payment.route('/api/v1.0/test-login')
@jwt_required()  # jwt_required has changed to jwt_required() in >=4.0
def test_login():
    current_user = get_current_user()  # return an account object from the user_loader_callback_loader
    return jsonify(logged_in_as=current_user.account_id), 200


@scb_payment.route('/verify-slip')
def verify_slip():
    list_type = request.args.get('list_type')
    return render_template('scb_payment_service/verify_slips.html', list_type=list_type)


@scb_payment.route('/slip/view/<int:slip_id>')
def view_slip_info(slip_id):
    slip = ScbPaymentRecord.query.get(slip_id)
    return render_template('scb_payment_service/view_slip_info.html', slip=slip)


@scb_payment.route('/api/verify-slip')
def get_verify_slip_data():
    list_type = request.args.get('list_type')
    query = ScbPaymentRecord.query
    if list_type is None:
        query = ScbPaymentRecord.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ScbPaymentRecord.customer1.like(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    if list_type == 'unsuccess':
        query = ScbPaymentRecord.query.filter_by(transaction_id=None)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['amount'] = u'{:.2f}'.format(item.amount)
        item_data['transaction_dateand_time'] = item_data['transaction_dateand_time'].strftime('%d-%m-%Y %H:%M:%S') if item_data['transaction_dateand_time'] else ''
        item_data['view_slip'] = '<a href="{}" class="button is-small is-rounded is-primary is-outlined">รายละเอียด</a>'.format(
            url_for('scb_payment.view_slip_info', slip_id=item.id))
        item_data['status'] = "จ่ายเงินสำเร็จ" if item.transaction_id else "ยังไม่ได้จ่ายเงิน"
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ScbPaymentRecord.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@scb_payment.route('/transaction-inquiry')
def transaction_inquiry():
    bill_payment_ref1 = request.args.get('bill_payment_ref1')
    bill_payment_ref2 = request.args.get('bill_payment_ref2')
    print(bill_payment_ref1)
    trnx = None
    if bill_payment_ref1 and bill_payment_ref2:
        trnx = ScbPaymentRecord.query.filter_by(bill_payment_ref1=bill_payment_ref1,
                                                bill_payment_ref2=bill_payment_ref2).first()
    elif bill_payment_ref1:
        trnx = ScbPaymentRecord.query.filter_by(bill_payment_ref1=bill_payment_ref1).first()

    if trnx:
        data = scb_qr30_inquiry(
            reference1=trnx.bill_payment_ref1,
            transaction_date=trnx.created_datetime.strftime("%Y-%m-%d"),
            event_code="00300100"
        )
        return jsonify(data)
    records = ScbPaymentRecord.query.all()
    return render_template('scb_payment_service/transaction_inquiry.html', records=records)


@scb_payment.route('/api/v1.0/check-payment')
@jwt_required()
def check_payment():
    bill_payment_ref1 = request.args.get('bill_payment_ref1')
    bill_payment_ref2 = request.args.get('bill_payment_ref2')
    if bill_payment_ref1 and bill_payment_ref2:
        trnx = ScbPaymentRecord.query.filter_by(bill_payment_ref1=bill_payment_ref1,
                                                bill_payment_ref2=bill_payment_ref2).first()
        if trnx:
            if trnx.payer_name is None and trnx.payer_account_number is None and trnx.sending_bank_code is None:
                inquiry_resp = scb_qr30_inquiry(
                    reference1=trnx.bill_payment_ref1,
                    transaction_date=trnx.created_datetime.strftime("%Y-%m-%d"),
                    event_code="00300100"
                )
                data = inquiry_resp.get('data') if isinstance(inquiry_resp, dict) else None
                if data:
                    trnx.payer_name = data.get('sender', {}).get('name')
                    trnx.payer_account_number = data.get('sender', {}).get('account', {}).get('value')
                    trnx.sending_bank_code = data.get('sendingBank')
                    trans_date_time = data.get('transDate') + ' ' + data.get('transTime')
                    trans_date_time = datetime.strptime(trans_date_time, '%Y%m%d %H:%M:%S')
                    trnx.transaction_dateand_time = trans_date_time
                    db.session.add(data)
                    db.session.commit()
            return jsonify({'data': {
                'payer_name': trnx.payer_name,
                'payer_account_number': trnx.payer_account_number,
                'sending_bank_code': trnx.sending_bank_code,
                'transaction_dateand_time': trnx.transaction_dateand_time,
                'bill_payment_ref1': trnx.bill_payment_ref1,
                'bill_payment_ref2': trnx.bill_payment_ref2,
                'transaction_id': trnx.transaction_id,
                'amount': trnx.amount
            }})
