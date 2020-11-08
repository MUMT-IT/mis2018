''' Retrieve publications from Scopus APIs and add them to the database.

'''

import os
import sys
import requests
import pprint
import time
import re
import json
import pandas as pd
from datetime import datetime
from collections import defaultdict
from pymongo import MongoClient

client = MongoClient()
db = client.tm_database
collection = db.pubstats


API_KEY = '871232b0f825c9b5f38f8833dc0d8691'

ITEM_PER_PAGE = 25
SLEEPTIME = 5

subj_areas = {'COMP', 'CENG', 'CHEM',
                'PHAR', 'AGRI', 'ARTS',
                'BIOC', 'BUSI', 'DECI',
                'DENT', 'EART', 'ECON',
                'ENER', 'ENGI', 'ENVI',
                'HEAL', 'IMMU', 'MATE',
                'MATH', 'MEDI', 'NEUR',
                'NURS', 'PHYS', 'PSYC',
                'SOCI', 'VETE', 'MULT'
                }


def add_author(authors, abstract):
    url = 'http://api.elsevier.com/content/search/author'
    if not authors:
        return None

    for au in authors:
        params = {'apiKey': API_KEY,
                    'query': 'auid({})'.format(au['authid']),
                    'httpAccept': 'application/json'}
        author = requests.get(url, params=params).json()
        author = author['search-results']['entry'][0]
        cur_affil = author.get('affiliation-current', {})
        preferred_name=author['preferred-name']['surname']+ ' ' +\
                                    author['preferred-name']['given-name']


def load(authors, year):
    '''authors: a list of authors in a list-like data structure

    '''

    for n, (_, auth) in enumerate(authors.iterrows(), start=1):
        try:
            finit = auth['FirstNameEn'].lower()[0]
            lastname = auth['LastNameEn'].lower()
            authname = auth['FirstNameEn'].lower() + ' ' + auth['LastNameEn'].lower()
        except AttributeError:
            continue  # ignore authors with no English name

        query = 'AUTHLASTNAME("%s") AUTHFIRST("%s") DOCTYPE(ar) PUBYEAR AFT %d' \
                % (lastname, finit, year)
        params = {'apiKey': API_KEY, 'query': query, 'httpAccept': 'application/json',
                'view': 'COMPLETE', 'field': 'dc:title,dc:identifier,author'}
        apikey = {'apiKey' : API_KEY}
        url = 'http://api.elsevier.com/content/search/scopus'

        authors_articles_sid = []
        r = requests.get(url, params=params).json()
        for article in r['search-results']['entry']:
            if 'author' in article:
                for author in article['author']:
                    try:
                        if auth['FirstNameEn'].lower() == author['given-name'].lower():
                            authors_articles_sid.append(
                                article['dc:identifier'].replace('SCOPUS_ID:', ''))
                    except AttributeError:
                        continue

        total_results = len(authors_articles_sid)
        print('{}. {} {} has {} articles'.\
                format(n, auth['FirstNameEn'],
                        auth['LastNameEn'], total_results))

        articles_dict = defaultdict(int)
        if total_results > 0:
            for scopus_id in authors_articles_sid:
                params = {'apiKey': API_KEY, 'query': query, 'httpAccept': 'application/json',
                        'view': 'FULL'}
                apikey = {'apiKey' : API_KEY}
                url = 'http://api.elsevier.com/content/abstract/scopus_id/' + scopus_id
                print('\t\t{}'.format(url))
                r = requests.get(url, params=params).json()
                try:
                    for sbj in r['abstracts-retrieval-response']['subject-areas']['subject-area']:
                        articles_dict[sbj['@abbrev']] += 1
                except:
                    print('Cannot retrieve subject areas of this article scopus ID={}.'.format(scopus_id))
                    pass

        for subj in subj_areas:
            stats = {'author': authname,
                            'articles': {
                                'field': subj,
                                'total': articles_dict[subj],
                                }
                            }

            inserted_id = collection.insert_one(stats).inserted_id
            # print('New stats added with id={}'.format(inserted_id))
        if n % 20 == 0:
            print('\t-=Taking a break...=-')
            time.sleep(SLEEPTIME)


def get_pub_counts(authors, year):
    '''authors: a list of authors in a list-like data structure

    '''

    active_authors = 0
    for n, (_, auth) in enumerate(authors.iterrows()):
        finit = auth['FirstNameEn'].lower()[0]
        lastname = auth['LastNameEn'].lower()
        authname = auth['FirstNameEn'].lower() + ' ' + auth['LastNameEn'].lower()

        query = 'AUTHLASTNAME("%s") AUTHFIRST("%s") DOCTYPE(ar)' % (lastname, finit)
        params = {'apiKey': API_KEY, 'query': query,
                    'httpAccept': 'application/json', 'view': 'COMPLETE'}
        apikey = {'apiKey' : API_KEY}
        url = 'http://api.elsevier.com/content/search/scopus'

        r = requests.get(url, params=params).json()
        total_results = int(r['search-results']['opensearch:totalResults'])

        print('{}. {} {} has {} articles'.\
                format(n, auth['FirstNameEn'], auth['LastNameEn'], total_results))

        if total_results > 0:
            active_authors += 1
        if n % 50 == 0:
            print('\t-=Taking a break...=-')
            time.sleep(SLEEPTIME)

    print('Total active authors = %d'.format(active_authors))


def main(infile, sheetno, year):
    data = pd.read_excel(infile, sheetname=sheetno)
    load(data.iloc[2753:][['FirstNameEn', 'LastNameEn']], year)


if __name__=='__main__':
    infile = sys.argv[1]
    sheetno = int(sys.argv[2])
    year = int(sys.argv[3])
    r = main(infile, sheetno, year)
