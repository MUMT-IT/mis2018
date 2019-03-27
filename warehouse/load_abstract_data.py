import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.automap import automap_base

POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')

dateformat = '%Y-%m-%d'

DWBase = automap_base()
DBBase = automap_base()

db_engine = create_engine('postgres+psycopg2://postgres:{}@pg/mumtmis_dev'
                         .format(POSTGRES_PASSWORD))

dw_engine = create_engine('postgres+psycopg2://postgres:{}@pg/mumtdw'
                       .format(POSTGRES_PASSWORD))

dw_session = Session(dw_engine)
db_session = Session(db_engine)

DWBase.prepare(dw_engine, reflect=True)
DBBase.prepare(db_engine, reflect=True)

Pub = DBBase.classes.research_pub

DateTable = DWBase.classes.dates
Abstract = DWBase.classes.research_abstracts

for pub in db_session.query(Pub).all():
    if pub.data.get('prism:coverDate', None):
        date_id = int(pub.data['prism:coverDate'].replace('-', ''))
    else:
        date_id = None

    _ab = dw_session.query(Abstract).filter_by(scopus_id=pub.scopus_id).first()
    if _ab:
        print('Abstract ID={} already exists'.format(_ab.scopus_id))
        continue

    ab = Abstract(
        scopus_id=pub.scopus_id,
        title=pub.data.get('dc:title', 'No title'),
        abstract=pub.data.get('dc:description', 'No abstract'),
        publication=pub.data.get('prism:publicationName', 'No publication name'),
        cited=int(pub.data.get('citedby-count', '0')),
        authors=pub.data.get('author')
    )

    if date_id:
        ab.date_id = dw_session.query(DateTable).get(date_id).date_id
    else:
        ab.date_id = None
    dw_session.add(ab)
    print('Abstract ID={} loaded to the data warehouse'.format(ab.scopus_id))

dw_session.commit()
