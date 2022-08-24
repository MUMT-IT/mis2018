import os

import requests
from flask import jsonify, request
from flask_jwt_extended import (create_access_token, get_jwt_identity, jwt_required, get_current_user)
from werkzeug.security import check_password_hash

from . import scb_payment
from .models import ScbPaymentServiceApiClientAccount
from ..main import csrf

AUTH_URL = 'https://api-sandbox.partners.scb/partners/sandbox/v1/oauth/token'
QRCODE_URL = 'https://api-sandbox.partners.scb/partners/sandbox/v1/payment/qrcode/create'
APP_KEY = os.environ.get('SCB_APP_KEY')
APP_SECRET = os.environ.get('SCB_APP_SECRET')
BILLERID = os.environ.get('BILLERID')
REQUEST_UID = os.environ.get('SCB_REQUEST_UID')


def generate_qrcode(amount, ref1, ref2, ref3):
    headers = {
        'Content-Type': 'application/json',
        'requestUId': REQUEST_UID,
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


@scb_payment.route('/api/v1.0/login', methods=['POST'])
@csrf.exempt
def login():
    client_id = request.get_json().get('client_id')
    client_secret = request.get_json().get('client_secret')
    client = ScbPaymentServiceApiClientAccount.query.get(client_id)
    if client:
        if check_password_hash(client._secret_hash, client_secret):
            return jsonify(access_token=create_access_token(identity=client_id))
        else:
            return jsonify({'message': 'Invalid client secret.'}), 403
    else:
        return jsonify({'message': 'Client account not found.'}), 404


@scb_payment.route('/api/v1.0/qrcode/create', methods=['POST'])
@csrf.exempt
def create_qrcode():
    amount = request.get_json().get('amount')
    ref1 = request.get_json().get('ref1')
    ref2 = request.get_json().get('ref2')
    if amount is None:
        return jsonify({'message': 'Amount is needed'}), 400
    data = generate_qrcode(amount, ref1=ref1, ref2=ref2, ref3='MXU')
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


@scb_payment.route('/api/v1.0/test-login')
@jwt_required  # jwt_required has changed to jwt_required() in >=4.0
def test_login():
    current_user = get_current_user()  # return an account object from the user_loader_callback_loader
    return jsonify(logged_in_as=current_user.account_id), 200
