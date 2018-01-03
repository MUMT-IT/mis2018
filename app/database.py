from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from . import meta, connect, engine

def create_db():
    users = Table('users', meta,
            Column('email', String, nullable=False, primary_key=True),
            extend_existing=True
            )

    kpis = Table('kpis', meta,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('owned_by', Integer, ForeignKey('orgs.id')),
            Column('created_by', String),
            Column('created_at', DateTime, server_default=func.now()),
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
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('name', String, nullable=False),
            Column('head', String),
            Column('parent', Integer, ForeignKey('orgs.id')),
            extend_existing=True
            )

    strategies = Table('strategies', meta,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('refno', String, nullable=False),
            Column('created_at', DateTime, server_default=func.now()),
            Column('content', String, nullable=False),
            Column('owner', Integer, ForeignKey('orgs.id'), nullable=False)
            )

    strategy_tactics = Table('strategy_tactics', meta,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('refno', String, nullable=False),
            Column('created_at', DateTime, server_default=func.now()),
            Column('content', String, nullable=False),
            Column('parent', Integer, ForeignKey('strategies.id'), nullable=False)
            )

    strategy_themes = Table('strategy_themes', meta,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('refno', String, nullable=False),
            Column('created_at', DateTime, server_default=func.now()),
            Column('content', String, nullable=False),
            Column('parent', Integer, ForeignKey('strategy_tactics.id'), nullable=False)
            )

    strategy_activities = Table('strategy_activities', meta,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('refno', String, nullable=False),
            Column('created_at', DateTime, server_default=func.now()),
            Column('content', String, nullable=False),
            Column('parent', Integer, ForeignKey('strategy_themes.id'), nullable=False)
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
        ins = orgs.insert().values(name=d['name'], head=head, parent=parent)
        result = connect.execute(ins)
        print(result.inserted_primary_key)


def load_strategy():
    import pandas as pd
    data  = pd.read_excel('kpi.xlsx', header=None,
                names=['id', 'content', 'owner_id'], sheet_name='strategy_list')
    strategies = meta.tables['strategies']
    for idx, rec in data.iterrows():
        ins = strategies.insert().values(
                refno=str(int(rec['id'])),
                owner=int(rec['owner_id']), content=rec['content'])
        result = connect.execute(ins)
        print(result.inserted_primary_key)


def load_tactics():
    import pandas as pd
    data = pd.read_excel('kpi.xlsx', header=0, sheet_name='tactic')
    strategy_tactics = meta.tables['strategy_tactics']
    for idx, rec in data.iterrows():
        ins = strategy_tactics.insert().values(
                refno=str(int(rec['tactic_refno'])),
                parent=int(rec['strategy_id']), content=rec['tactic_content'])
        result = connect.execute(ins)
        print(result.inserted_primary_key)


def load_themes():
    import pandas as pd
    data = pd.read_excel('kpi.xlsx', header=0, sheet_name='theme')
    strategy_themes = meta.tables['strategy_themes']
    for idx, rec in data.iterrows():
        ins = strategy_themes.insert().values(
                refno=str(int(rec['theme_refno'])),
                parent=int(rec['tactic_id']), content=rec['theme_content'])
        result = connect.execute(ins)
        print(result.inserted_primary_key)


def load_activities():
    import pandas as pd
    data = pd.read_excel('kpi.xlsx', header=0, sheet_name='activity')
    strategy_activities = meta.tables['strategy_activities']
    for idx, rec in data.iterrows():
        ins = strategy_activities.insert().values(
                refno=str(int(rec['activity_refno'])),
                parent=int(rec['theme_id']), content=rec['activity_content'])
        result = connect.execute(ins)
        print(result.inserted_primary_key)