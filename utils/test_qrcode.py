import requests
import sys

client_id = sys.argv[1]
client_secret = sys.argv[2]
base_url = 'https://mumtmis.herokuapp.com/scb_payment/api/v1.0'
resp = requests.post(base_url + '/login', json={'client_id': client_id, 'client_secret': client_secret})
print(resp.status_code)
print(resp.json())
access_token = resp.json().get('access_token')
print(access_token)
resp = requests.post(base_url + '/qrcode/create', json={'ref1': 'ABCE', 'ref2': 'DEFG', 'amount': '600.55', 'customer1':
    'K.YADA', 'service': 'Test SCB Payment Service'}, headers={'Authorization': 'Bearer ' + access_token})
print(resp.status_code)
print(resp.json())
with open("imageToSave.png", "wb") as fh:
    fh.write(resp.json()['data']['qrImage'].decode('base64'))
