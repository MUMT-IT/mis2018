import os
from decimal import Decimal

import pytz
import requests
from flask import jsonify, request, flash

from . import scb_payment
from .models import SCBPaymentRecord
from ..main import csrf, db
import dateutil.parser


AUTH_URL = 'https://api-sandbox.partners.scb/partners/sandbox/v1/oauth/token'
QRCODE_URL = 'https://api-sandbox.partners.scb/partners/sandbox/v1/payment/qrcode/create'
APP_KEY = os.environ.get('SCB_APP_KEY')
APP_SECRET = os.environ.get('SCB_APP_SECRET')
BILLERID = os.environ.get('BILLERID')
REF3_PREFIX = os.environ.get('REF3_PREFIX')


def generate_qrcode(amount, ref1, ref2, ref3, request_uid):
    headers = {
        'Content-Type': 'application/json',
        'requestUId': request_uid,
        'resourceOwnerId': APP_KEY
    }
    response = requests.post(AUTH_URL, headers=headers, json={
        'applicationKey': APP_KEY,
        'applicationSecret': APP_SECRET
    })
    response_data = response.json()
    access_token = response_data['data']['accessToken']

    headers['authorization'] = 'Bearer {}'.format(access_token)

    qrcode_resp = requests.post(QRCODE_URL, headers=headers, json={
        'qrType': 'PP',
        'amount': '{}'.format(amount),
        'ppType': 'BILLERID',
        'ppId': BILLERID,
        'ref1': ref1,
        'ref2': ref2,
        'ref3': ref3,
    })
    if qrcode_resp.status_code == 200:
        qr_image = qrcode_resp.json()['data']['qrImage']
        return {'qrImage': qr_image}
    else:
        return None


@scb_payment.route('/api/v1.0/qrcode/create', methods=['POST'])
@csrf.exempt
def create_qrcode():
    amount = request.get_json().get('amount')
    if amount is None:
        return jsonify({'message': 'Amount is needed'}), 400
    data = generate_qrcode(amount, ref1='12345678', ref2='987654321', ref3=REF3_PREFIX)
    if data:
        return jsonify({'data': data})
    else:
        return jsonify({'message': 'Error happened.'}), 500


@scb_payment.route('/api/v1.0/payment-confirm', methods=['POST'])
@csrf.exempt
def confirm_payment():
    print(request.method)
    data = request.get_json()
    print(data)
    new_record = SCBPaymentRecord()
    new_record.payer_account_number = data.get('payerAccountNumber')
    new_record.payee_proxy_type = data.get('payeeProxyType')
    new_record.sending_bank_code = data.get('sendingBankCode')
    new_record.payee_proxy_id = data.get('payeeProxyId')
    new_record.bill_payment_ref3 = data.get('billPaymentRef3')
    new_record.currency_code = data.get('currencyCode')
    new_record.transaction_type = data.get('transactionType')
    new_record.transaction_date_time = dateutil.parser.isoparse(data.get('transactionDateandTime')).astimezone(pytz.utc)
    new_record.channel_code = data.get('channelCode')
    new_record.bill_payment_ref1 = data.get('billPaymentRef1')
    new_record.amount = Decimal(data.get('amount'))
    new_record.payer_proxy_type = data.get('payerProxyType')
    new_record.payee_name = data.get('payeeName')
    new_record.receiving_bank_code = data.get('receivingBankCode')
    new_record.payee_account_number = data.get('payeeAccountNumber')
    new_record.payer_proxy_id = data.get('payerProxyId')
    new_record.bill_payment_ref2 = data.get('billPaymentRef2')
    new_record.transaction_id = data.get('transactionId')
    new_record.payer_name = data.get('payerName')
    db.session.add(new_record)
    db.session.commit()
    flash('New record has been added.', 'success')
    return jsonify({'message': 'hello'})
