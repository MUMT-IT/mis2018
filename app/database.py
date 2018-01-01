from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, Boolean
from . import meta, connect, engine

def create_db():
    users = Table('users', meta,
            Column('email', String, nullable=False, primary_key=True),
            extend_existing=True
            )

    kpis = Table('kpis', meta,
            Column('id', Integer, primary_key=True),
            Column('owned_by', Integer, ForeignKey('orgs.id')),
            Column('created_by', String),
            Column('created_at', DateTime, default=datetime.now),
            Column('name', String, nullable=False),
            Column('refno', String),
            Column('intent', String),
            Column('frequency', Integer),
            Column('unit', String),
            Column('source', String),
            Column('available', Boolean),
            Column('availability', String),
            Column('formula', String),
            Column('keeper', String, ForeignKey('users.email')),
            Column('note', String),
            Column('target', String),
            Column('target_source', String),
            Column('target_setter', String),
            Column('target_reporter', String),
            Column('target_account', String),
            Column('reporter', String),
            Column('consult', String),
            Column('account', String),
            Column('informed', String),
            Column('pfm_account', String),
            Column('pfm_resposible', String),
            Column('pfm_consult', String),
            Column('pfm_informed', String),
            extend_existing=True
            )

    orgs = Table('orgs', meta,
            Column('id', Integer, primary_key=True),
            Column('name', String, nullable=False),
            Column('head', String),
            Column('parent', Integer, ForeignKey('orgs.id')),
            extend_existing=True
            )

    meta.create_all(engine)


def load_orgs():
    import pandas as pd
    data  = pd.read_excel('staff.xlsx', names=['id', 'name', 'parent', 'head'],  header=None)
    orgs = meta.tables['orgs']
    for row in data.iterrows():
        idx, d = row
        parent = None if pd.isna(d['parent']) else int(d['parent'])
        head = None if pd.isna(d['head']) else d['head']
        ins = orgs.insert().values(id=int(d['id']), name=d['name'],
                head=head, parent=parent)
        result = connect.execute(ins)
        print(result.inserted_primary_key)