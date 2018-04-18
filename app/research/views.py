import os
import datetime
from collections import namedtuple

import requests
from flask import request, render_template, jsonify
from . import researchbp as research
from models import APIKey, ResearchPub
from ..staff.models import StaffAccount
from ..main import db

Author = namedtuple('Author', ['email', 'firstname', 'lastname'])

usr = os.environ.get('PROXY_USER')
pwd = os.environ.get('PROXY_PASSWORD')

ITEM_PER_PAGE = 25
SLEEPTIME = 5

def get_key(service):
    api_key = db.session.query(APIKey).filter(APIKey.service==service).first().key
    return api_key

def download_scopus_pub_by_author(author, api_key, year):
    # TODO: need to figure out the proxy IP and port
    # proxy_dict = {'http': 'http://{}:{}@proxy.mahidol/'.format(usr,pwd) }

    query = 'AUTHLASTNAME("%s") AUTHFIRST("%s") DOCTYPE(ar) PUBYEAR AFT %d' \
            % (author.lastname, author.firstname[0], year)
    params = {'apiKey': api_key, 'query': query, 'httpAccept': 'application/json',
            'view': 'COMPLETE', 'field': 'dc:title,dc:identifier,author'}
    url = 'http://api.elsevier.com/content/search/scopus'

    authors_articles_sid = []
    r = requests.get(url, params=params).json()
    for article in r['search-results']['entry']:
        if 'author' in article:
            for au in article['author']:
                try:
                    if author.firstname.lower() == au['given-name'].lower():
                        authors_articles_sid.append(
                            article['dc:identifier'].replace('SCOPUS_ID:', ''))
                except AttributeError:
                    continue

        total_results = len(authors_articles_sid)
        new_articles = []
        if total_results > 0:
            for scopus_id in authors_articles_sid:
                existing_pub = db.session.query(ResearchPub).filter(ResearchPub.uid==scopus_id).first()
                if existing_pub:
                    continue
                params = {'apiKey': api_key, 'query': query, 'httpAccept': 'application/json',
                        'view': 'FULL'}
                url = 'http://api.elsevier.com/content/abstract/scopus_id/' + scopus_id
                r = requests.get(url, params=params).json()
                rp = ResearchPub(author_id=author.email, uid=scopus_id, data=r, indexed_db='scopus')
                db.session.add(rp)
                db.session.commit()
                new_articles.append(r)
    return {'author': author, 'total': total_results, 'new_articles': new_articles}


@research.route('/scopus/retrieve')
def retrieve_scopus_data():
    authors = []

    year = request.args.get('year', 2015)
    if year is None:
        year = datetime.datetime.today().year

    author_email = request.args.get('author_email', None)
    if author_email is not None:
        author = db.session.query(StaffAccount).filter(StaffAccount.email==author_email).first()
        if not author:
            return 'No author with the given email found in the database.'
        firstname = author.personal_info.en_firstname.lower()
        lastname = author.personal_info.en_lastname.lower()
        authors.append(Author(author.email, firstname, lastname))
    else:
        for author in db.session.query(StaffAccount):
            firstname = author.personal_info.en_firstname.lower()
            lastname = author.personal_info.en_lastname.lower()
            authors.append(Author(author.email, firstname, lastname))
    api_key = get_key('SCOPUS')

    results = []
    for author in authors:
        res = download_scopus_pub_by_author(author, api_key, year)
        results.append(res)
    return jsonify(results)