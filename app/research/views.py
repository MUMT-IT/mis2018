import os
import datetime
import time
from collections import defaultdict

import pandas
import requests
from flask import request, render_template, jsonify
from pandas import DataFrame
from . import researchbp as research
from app.research.models import APIKey, ResearchPub, Country, Author, Affiliation, ScopusAuthorID, SubjectArea
from app.staff.models import StaffPersonalInfo
from app.main import db, json_keyfile, csrf
from sqlalchemy import extract

usr = os.environ.get('PROXY_USER')
pwd = os.environ.get('PROXY_PASSWORD')
SCOPUS_API_KEY = os.environ.get('SCOPUS_API_KEY')

ITEM_PER_PAGE = 25
SLEEPTIME = 5

import gspread
import sys
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive']

def get_google_credential(json_keyfile):
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
    return gspread.authorize(credentials)

def get_key(service):
    api_key = db.session.query(APIKey).filter(APIKey.service==service).first().key
    return api_key

def download_scopus_pub(api_key, year):
    # TODO: need to figure out the proxy IP and port
    # proxy_dict = {'http': 'http://{}:{}@proxy.mahidol/'.format(usr,pwd) }

    '''
    query = 'AFFILORG("faculty of medical technology" "mahidol university") DOCTYPE(ar) PUBYEAR = %d' \
            % (int(year))
    '''
    query = 'AFFILORG("faculty of medical technology" "mahidol university") PUBYEAR = %d' \
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
        existing_pub = db.session.query(ResearchPub).filter(ResearchPub.scopus_id==scopus_id).first()
        if existing_pub:
            print('\t\t\t{} exists..updating a citation count..'.format(scopus_id))
            existing_pub.cited_count = citation_count
            db.session.add(existing_pub)
            db.session.commit()
            continue
        rp = ResearchPub(scopus_id=scopus_id, data=r, cited_count=citation_count)
        db.session.add(rp)
        db.session.commit()
        # TODO: add article to staff.
        '''
        for _author in r['abstracts-retrieval-response']['authors']['author']:
            _firstname = _author.get('ce:given-name', '').title()
            _lastname = _author.get('ce:surname', '').title()
            _au = db.session.query(StaffPersonalInfo)\
                .filter(StaffPersonalInfo.en_firstname==_firstname,
                        StaffPersonalInfo.en_lastname==_lastname).first()
            if _au:
                author_account = _au.staff_account
                existing_pubs = set([p.scopus_id for p in author_account.pubs])
                if rp.scopus_id not in existing_pubs:
                    author_account.pubs.append(rp)
                    db.session.add(author_account)
        db.session.commit()
        '''
    return {'status': 'done'}


@research.route('/scopus/retrieve')
def retrieve_scopus_data():
    year = request.args.get('year', None)

    if year is None:
        year = datetime.datetime.today().year

    api_key = SCOPUS_API_KEY

    res = download_scopus_pub(api_key, year)
    return jsonify({'status': 'ok'})


@research.route('/scopus/pubs')
def display_total_pubs():
    pubs = []
    article_years = defaultdict(int)
    citation_years = defaultdict(int)
    cum_citations = 0
    cum_citation_years = defaultdict(int)
    years = set()
    for pub in db.session.query(ResearchPub):
        first_author = pub.data['abstracts-retrieval-response']['coredata']['dc:creator']['author'][0]
        coverdate = pub.data['abstracts-retrieval-response']['coredata']['prism:coverDate']
        citation = int(pub.data['abstracts-retrieval-response']['coredata']['citedby-count'])
        coveryear = int(coverdate.split('-')[0])
        years.add(coveryear)
        article_years[coveryear] += 1
        citation_years[coveryear] += citation
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
    for year in sorted(years):
        cum_citations += citation_years[year]
        cum_citation_years[year] += cum_citations

    return render_template('research/pubs.html', pubs=pubs,
                years=sorted(years), citation_years=citation_years,
                article_years=article_years, cum_citation_years=cum_citation_years)


@research.route('/view/author/<int:perid>')
def view_researcher(perid):
    person = StaffPersonalInfo.query.get(perid)
    return render_template('research/researcher_profile.html', person=person)


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

@research.route('/api/funding')
def get_funding_data():
    gc = get_google_credential(json_keyfile)
    sheet = gc.open_by_key('1RolhNZwWcj-GVd4SQhXA15i-OrpShpw01F3apaoq0nQ').sheet1
    values = sheet.get_all_values()
    df = DataFrame(values[1:], columns=values[0])
    data = []
    for idx, row in df.iterrows():
        pairs = []
        for key in row[df.columns[1:]].keys():
            pairs.append({
                'topic': key,
                'value': row[key]
            })
        data.append({
            'year': row['year'],
            'data': pairs
        })
    return jsonify(data)


@research.route('/funding')
def show_funding():
    return render_template('research/funding.html')


@research.route('/api/cost')
def get_cost_data():
    gc = get_google_credential(json_keyfile)
    sheet = gc.open_by_key('1o_HMdBtUnZtGDZ4ZcybrzQantDa-NRxT-Txc_eDaQ9g').sheet1
    values = sheet.get_all_values()
    df = DataFrame(values[1:], columns=values[0])
    data = []
    for idx, row in df.iterrows():
        pairs = []
        for key in row[df.columns[1:]].keys():
            pairs.append({
                'topic': key,
                'value': row[key]
            })
        data.append({
            'year': row['year'],
            'data': pairs
        })
    return jsonify(data)


@research.route('/cost')
def show_cost():
    return render_template('research/cost.html')


@research.route('/api/scopus_cum')
def get_scopus_cum_data():
    gc = get_google_credential(json_keyfile)
    sheet = gc.open_by_key('154-IDTfFSWxOnx61XIOYffp8YDbMw5I9dAiYD_hIMBM').sheet1
    values = sheet.get_all_values()
    df = DataFrame(values[1:], columns=values[0])
    data = []
    for idx, row in df.iterrows():
        pairs = []
        for key in row[df.columns[1:]].keys():
            pairs.append({
                'topic': key,
                'value': row[key]
            })
        data.append({
            'year': row['year'],
            'data': pairs
        })
    return jsonify(data)


@research.route('/scopus_cum')
def show_scopus_cum():
    return render_template('research/scopus_cum.html')


@research.route('/api/citation_cum')
def get_citation_cum_data():
    gc = get_google_credential(json_keyfile)
    sheet = gc.open_by_key('196Fqeg7NUUYCLotWv7yrQrnqA8DzNn0Ts1EkB8U8Po0').sheet1
    values = sheet.get_all_values()
    df = DataFrame(values[1:], columns=values[0])
    data = []
    for idx, row in df.iterrows():
        pairs = []
        for key in row[df.columns[1:]].keys():
            pairs.append({
                'topic': key,
                'value': row[key]
            })
        data.append({
            'year': row['year'],
            'data': pairs
        })
    return jsonify(data)


@research.route('/citation_cum')
def show_citation_cum():
    return render_template('research/citation_cum.html')


@research.route('/api/datamining_cum')
def get_datamining_cum_data():
    gc = get_google_credential(json_keyfile)
    sheet = gc.open_by_key('14E4G8N2uZmXiZvnZkWV7Sg1lGWE4E-HTHBV9yhzpPxk').sheet1
    values = sheet.get_all_values()
    df = DataFrame(values[1:], columns=values[0])
    data = []
    for idx, row in df.iterrows():
        pairs = []
        for key in row[df.columns[1:]].keys():
            pairs.append({
                'topic': key,
                'value': row[key]
            })
        data.append({
            'year': row['year'],
            'data': pairs
        })
    return jsonify(data)


@research.route('/datamining_cum')
def show_datamining_cum():
    return render_template('research/datamining_cum.html')


@research.route('/dashboard')
def dashboard():
    return render_template('research/dashboard.html')


@research.route('/dashboard/tables')
def dashboard_tables():
    return render_template('research/pub_tables.html')


@research.route('/api/articles/researcher/<int:perid>/count')
def get_article_count_researcher(perid):
    personal_info = StaffPersonalInfo.query.get(int(perid))
    data = []
    df = pandas.read_sql_query("SELECT extract(year FROM cover_date) "
                               "AS year, COUNT(*), SUM(cited_count) AS cited "
                               "FROM research_pub INNER JOIN pub_author_assoc AS pa ON id=pa.pub_id WHERE pa.author_id={} "
                               "GROUP BY year ORDER BY year".format(personal_info.research_author.id),
                               con=db.engine)

    df['cumcited'] = df['cited'].cumsum()
    del df['cited']
    data.append(df.columns.tolist())
    for idx, row in df.iterrows():
        data.append(row.tolist())

    return jsonify(data)


@research.route('/api/articles/researcher/<int:perid>')
def get_articles_researcher(perid):
    personal_info = StaffPersonalInfo.query.get(int(perid))
    articles = []
    author = Author.query.filter_by(personal_info=personal_info).first()
    if author:
        for ar in author.papers:
            authors = []
            for au in ar.authors:
                authors.append({
                    'id': au.id,
                    'personal_info_id': au.personal_info_id,
                    'firstname': au.firstname,
                    'lastname': au.lastname
                })
            articles.append({
                'id': ar.scopus_id,
                'title': ar.title,
                'cover_date': ar.cover_date,
                'citedby_count': ar.citedby_count,
                'doi': ar.doi,
                'authors': authors,
                'abstract': ar.abstract,
            })
    return jsonify(articles)


@research.route('/api/articles/count')
def get_article_count():
    data = []
    df = pandas.read_sql_query("SELECT extract(year FROM cover_date) "
                               "AS year, COUNT(*), SUM(cited_count) AS cited "
                               "FROM research_pub GROUP BY year ORDER BY year", con=db.engine)
    df['cumcited'] = df['cited'].cumsum()
    del df['cited']
    data.append(df.columns.tolist())
    for idx, row in df.iterrows():
        data.append(row.tolist())

    return jsonify(data)


@research.route('/api/articles/test')
def add_article_test():
    if request.method == 'POST':
        print('getting posted..')
        data = request.get_json()
        time.sleep(5)
        return jsonify(data)


@research.route('/api/articles', methods=['GET', 'POST'])
@csrf.exempt
def add_article():
    current_year = request.args.get('year')
    max_pubs = request.args.get('max_pubs', None, type=int)
    if not current_year:
        current_year = datetime.datetime.today().year
    else:
        current_year = int(current_year)

    if request.method == 'GET':
        articles = []
        for ar in ResearchPub.query.filter(extract('year', ResearchPub.cover_date) == current_year)\
                .order_by(ResearchPub.cover_date.desc()):
            authors = []
            for au in ar.authors:
                authors.append({
                    'id': au.id,
                    'personal_info_id': au.personal_info_id,
                    'firstname': au.firstname,
                    'lastname': au.lastname
                })
            articles.append({
                'id': ar.scopus_id,
                'title': ar.title,
                'cover_date': ar.cover_date,
                'citedby_count': ar.citedby_count,
                'scopus_link': ar.scopus_link,
                'publication_name': ar.publication_name,
                'doi': ar.doi,
                'authors': authors,
                'abstract': ar.abstract,
            })
            if max_pubs and len(articles) == max_pubs:
                break
        return jsonify(articles)

    if request.method == 'POST':
        data = request.get_json()
        pub = ResearchPub.query.filter_by(scopus_id=data['scopus_id']).first()
        if not pub:
            pub = ResearchPub(
                scopus_id=data.get('scopus_id'),
                citedby_count=data.get('citedby_count'),
                title=data.get('title'),
                cover_date=datetime.datetime.strptime(data.get('cover_date'), '%Y-%m-%d'),
                abstract=data.get('abstract'),
                doi=data.get('doi'),
                scopus_link=data.get('scopus_link'),
                publication_name=data.get('publication_name')
            )
        else:
            # update the citation number and cover date because it can change.
            pub.citedby_count = data.get('citedby_count')
            pub.cover_date=datetime.datetime.strptime(data.get('cover_date'), '%Y-%m-%d'),

        for subj in data['subject_areas']:
            s = SubjectArea.query.get(subj['code'])
            if not s:
                s = SubjectArea(id=subj['code'],
                                area=subj['area'],
                                abbr=subj['abbreviation'])
                db.session.add(s)
            pub.areas.append(s)

        for author in data['authors']:
            scopus_id = ScopusAuthorID.query.get(author.get('author_id'))
            personal_info = StaffPersonalInfo.query\
                .filter_by(en_firstname=author['firstname'],
                           en_lastname=author['lastname']).first()
            if author.get('afid'):
                affil = Affiliation.query.get(author.get('afid'))
            else:
                affil = None
            country = Country.query.filter_by(name=author.get('country', 'Unknown')).first()
            if not country:
                country = Country(name=author.get('country', 'Unknown'))
                db.session.add(country)
            if not affil and author.get('afid'):
                affil = Affiliation(id=author.get('afid'),
                                    name=author.get('afname', 'Unknown'),
                                    country=country)
                db.session.add(affil)
            if scopus_id:
                if author.get('afid'):
                    # update the current affiliation
                    scopus_id.author.affil_id = author.get('afid')
            else:
                scopus_id = ScopusAuthorID(id=author.get('author_id'))
                author_ = Author.query.filter_by(firstname=author.get('firstname'),
                                                 lastname=author.get('lastname')
                                                 ).first()
                if not author_:
                    author_ = Author(firstname=author.get('firstname'),
                                     lastname=author.get('lastname'),
                                     affil_id=author.get('afid'),
                                     h_index=int(author.get('h_index')) if author.get('h_index') else None,
                                     personal_info=personal_info
                                     )
                scopus_id.author = author_
            scopus_id.author.h_index = int(author.get('h_index')) if author.get('h_index') else None
            pub.authors.append(scopus_id.author)
            db.session.add(scopus_id)
        print('saving publication {}'.format(pub.title[:30]))
        db.session.add(pub)

        db.session.commit()

        return jsonify(data)


@research.route('/api/articles/subjareas/count')
def subject_areas_count():
    current_year = request.args.get('year')
    if not current_year:
        current_year = datetime.datetime.today().year
    else:
        current_year = int(current_year)

    query = ('SELECT count(*), EXTRACT(year FROM cover_date) AS YEAR, abbr FROM research_pub'\
            ' INNER JOIN pub_subjarea_assoc AS sbj ON sbj.pub_id=id '
             'INNER JOIN research_subject_areas AS ra ON ra.id=sbj.subj_id '
             'WHERE EXTRACT(year FROM cover_date)={} GROUP BY abbr, year;'.format(current_year))
    df = pandas.read_sql_query(query, con=db.engine)
    data = []
    data.append(['abbr', 'count'])
    for idx, row in df.iterrows():
        data.append([
            row['abbr'],
            row['count']
        ])
    return jsonify(data)


@research.route('/api/articles/researchers/ratio')
def article_researcher_ratio():
    current_year = request.args.get('year')
    if not current_year:
        current_year = datetime.datetime.today().year
    else:
        current_year = int(current_year)
    researchers = pandas.read_sql_query('SELECT COUNT(*) FROM staff_personal_info '
                                        'WHERE academic_staff=TRUE AND retired IS NOT TRUE;',
                                        con=db.engine)
    articles = pandas.read_sql_query('SELECT COUNT(*) FROM research_pub '
                                     'WHERE EXTRACT (year from cover_date) = {};'.format(current_year),
                                     con=db.engine)
    return jsonify({'ratio': f'{float(researchers.squeeze()/float(articles.squeeze())):.2f}',
                    'articles': int(articles.squeeze()),
                    'researchers': int(researchers.squeeze())})


@research.route('/api/articles/researchers/countries')
def article_researcher_country():
    current_year = request.args.get('year')
    if not current_year:
        current_year = datetime.datetime.today().year
    else:
        current_year = int(current_year)

    df = pandas.read_sql_query('select count(*),research_countries.name from research_authors '
                               'inner join pub_author_assoc on research_authors.id=pub_author_assoc.author_id '
                               'inner join research_pub on pub_author_assoc.pub_id=research_pub.id '
                               'inner join research_affils on research_authors.affil_id=research_affils.id '
                               'inner join research_countries on research_affils.country_id=research_countries.id '
                               'where extract(year from cover_date) = {} group by 2;'.format(current_year),
                               con=db.engine)
    data = [['Country', 'Authors']]
    for idx, row in df.iterrows():
        if row['name'] != 'Thailand':
            data.append([row['name'], row['count']])
    return jsonify(data)


