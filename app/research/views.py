import os
import time
import datetime
import pprint
from collections import namedtuple, defaultdict

import requests
from flask import request, render_template, jsonify
from . import researchbp as research
from models import APIKey, ResearchPub
from ..staff.models import StaffAccount, StaffPersonalInfo
from ..main import db

Author = namedtuple('Author', ['email', 'firstname', 'lastname'])

usr = os.environ.get('PROXY_USER')
pwd = os.environ.get('PROXY_PASSWORD')

ITEM_PER_PAGE = 25
SLEEPTIME = 5

def get_key(service):
    api_key = db.session.query(APIKey).filter(APIKey.service==service).first().key
    return api_key

def download_scopus_pub(api_key, year):
    # TODO: need to figure out the proxy IP and port
    # proxy_dict = {'http': 'http://{}:{}@proxy.mahidol/'.format(usr,pwd) }

    '''
    query = 'AUTHLASTNAME("%s") AUTHFIRST("%s") DOCTYPE(ar) PUBYEAR = %d' \
            % (author.lastname, author.firstname[0], int(year))
    '''
    query = 'AFFILORG("faculty of medical technology" "mahidol university") DOCTYPE(ar) PUBYEAR = %d' \
            % (int(year))
    params = {'apiKey': api_key, 'query': query, 'httpAccept': 'application/json',
            'view': 'COMPLETE', 'field': 'dc:title,dc:identifier,author'}
    url = 'http://api.elsevier.com/content/search/scopus'

    r = requests.get(url, params=params).json()
    total_results = int(r['search-results']['opensearch:totalResults'])
    print('Total {} article(s) found.'.format(total_results))
    page = 0
    article_ids = []
    for start in range(0, total_results+1, ITEM_PER_PAGE):
        print('\tStarting at {}'.format(start))
        print('\tDownloading set {}..'.format(page))
        page += 1
        params = {'apiKey': api_key,
                    'query': query,
                    'httpAccept': 'application/json',
                    'view': 'COMPLETE',
                    'field': 'dc:title,dc:identifier,author',
                    'count': ITEM_PER_PAGE,
                    'start': start
                }
        r = requests.get(url, params=params).json()
        if 'search-results' in r:
            for article in r['search-results']['entry']:
                try:
                    article_ids.append(article['dc:identifier'].replace('SCOPUS_ID:', ''))
                except AttributeError:
                    continue

    print('total article IDs = {}'.format(len(article_ids)))

    for n,scopus_id in enumerate(article_ids, start=1):
        if n % 10 == 0:
            print('\t\ttaking a break...')
            time.sleep(5)
        print('\t\tfetching data for article no.{} ID: {}...'.format(n,scopus_id))
        params = {'apiKey': api_key, 'query': query, 'httpAccept': 'application/json',
                'view': 'FULL'}
        url = 'http://api.elsevier.com/content/abstract/scopus_id/' + scopus_id
        r = requests.get(url, params=params).json()
        citation_count = int(r['abstracts-retrieval-response']['coredata']['citedby-count'])
        existing_pub = db.session.query(ResearchPub).filter(ResearchPub.uid==scopus_id).first()
        if existing_pub:
            print('\t\t\t{} exists..updating a citation count..'.format(scopus_id))
            existing_pub.citation_count = citation_count
            db.session.add(existing_pub)
            db.session.commit()
            continue
        pubdate = r['abstracts-retrieval-response']['coredata']['prism:coverDate']
        pubyear = int(pubdate.split('-')[0])
        pubmonth = int(pubdate.split('-')[1])
        rp = ResearchPub(uid=scopus_id,
                            citation_count=citation_count,
                            data=r,
                            indexed_db='scopus',
                            pubmonth=pubmonth,
                            pubyear=pubyear)
        db.session.add(rp)
        db.session.commit()
        for _author in r['abstracts-retrieval-response']['authors']['author']:
            _firstname = _author.get('ce:given-name', '').title()
            _lastname = _author.get('ce:surname', '').title()
            _au = db.session.query(StaffPersonalInfo)\
                .filter(StaffPersonalInfo.en_firstname==_firstname,
                        StaffPersonalInfo.en_lastname==_lastname).first()
            if _au:
                author_account = _au.staff_account
                existing_pubs = set([p.uid for p in author_account.pubs])
                if rp.uid not in existing_pubs:
                    author_account.pubs.append(rp)
                    db.session.add(author_account)
        db.session.commit()
    return {'status': 'done'}


@research.route('/scopus/retrieve')
def retrieve_scopus_data():
    year = request.args.get('year', None)

    if year is None:
        year = datetime.datetime.today().year

    api_key = get_key('SCOPUS')

    res = download_scopus_pub(api_key, year)
    return jsonify({'status': 'ok'})


@research.route('/scopus/pubs')
def display_total_pubs():
    pubs = []
    years = defaultdict(int)
    citation_years = defaultdict(int)
    for pub in db.session.query(ResearchPub):
        first_author = pub.data['abstracts-retrieval-response']['coredata']['dc:creator']['author'][0]
        coverdate = pub.data['abstracts-retrieval-response']['coredata']['prism:coverDate']
        citation = int(pub.data['abstracts-retrieval-response']['coredata']['citedby-count'])
        coveryear = int(coverdate.split('-')[0])
        years[coveryear] += 1
        citation_years[coveryear] += int(citation)
        authors = []
        for author in pub.data['abstracts-retrieval-response']['authors']['author']:
            authors.append({
                'firstname': author.get('ce:given-name', ''),
                'lastname': author.get('ce:surname', '')
            })

        title = pub.data['abstracts-retrieval-response']['coredata']['dc:title']
        pub = {
            'first_author': first_author,
            'title': title,
            'authors': authors,
            'coveryear': coveryear,
            'citation': citation,
            }
        pubs.append(pub)
    return render_template('research/pubs.html', pubs=pubs,
                years=years, citation_years=citation_years)


@research.route('/api/scopus/pubs/yearly')
def display_yearly_pubs():
    years = defaultdict(int)
    citation_years = defaultdict(int)
    for pub in db.session.query(ResearchPub):
        coverdate = pub.data['abstracts-retrieval-response']['coredata']['prism:coverDate']
        # citation = int(pub.data['abstracts-retrieval-response']['coredata']['citedby-count'])
        coveryear = int(coverdate.split('-')[0])
        years[coveryear] += 1
        # citation_years[coveryear] += int(citation)
    labels = []
    data = []
    for yr in sorted(years.keys()):
        labels.append(str(yr))
        data.append(years[yr])
    return jsonify({'labels': labels, 'data': data})
