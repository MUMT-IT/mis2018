import requests
from . import researchbp as research
from models import *

API_KEY = '871232b0f825c9b5f38f8833dc0d8691'

@research.route('/scopus/retrieve')
def retrieve_scopus_data():
    firstname = request.args.get('firstname', None)
    lastname = request.args.get('lastname', None)
    return 'hello'