import os

import requests
from flask import jsonify, request

from . import scb_payment
from ..main import csrf

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
    return jsonify({'message': 'hello'})
