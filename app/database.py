from datetime import datetime
from sqlalchemy.sql import func
from main import db
from models import (Org, Strategy, StrategyTactic,
                        StrategyTheme, StrategyActivity)

def load_orgs():
    import pandas as pd
    data  = pd.read_excel('staff.xlsx', names=['id', 'name', 'parent', 'head'],  header=None)
    for row in data.iterrows():
        idx, d = row
        parent = None if pd.isna(d['parent']) else int(d['parent'])
        head = None if pd.isna(d['head']) else d['head']
        if not parent:
            org = Org(name=d['name'], head=head, parent=parent)
        else:
            parent = Org.query.get(parent)
            org = Org(name=d['name'], head=head, parent=parent)
        db.session.add(org)
        db.session.commit()


def load_strategy():
    import pandas as pd
    data  = pd.read_excel('kpi.xlsx', header=None,
                names=['id', 'content', 'owner_id'], sheet_name='strategy_list')
    for idx, rec in data.iterrows():
        org = Org.query.get(rec['owner_id'])
        s = Strategy(refno=str(rec['id']), org=org, content=rec['content'])
        db.session.add(s)
    db.session.commit()


def load_tactics():
    import pandas as pd
    data = pd.read_excel('kpi.xlsx', header=0, sheet_name='tactic')
    for idx, rec in data.iterrows():
        s = Strategy.query.get(rec['strategy_id'])
        t = StrategyTactic(refno=str(int(rec['tactic_refno'])),
                        strategy=s, content=rec['tactic_content'])
        db.session.add(t)
    db.session.commit()


def load_themes():
    import pandas as pd
    data = pd.read_excel('kpi.xlsx', header=0, sheet_name='theme')
    for idx, rec in data.iterrows():
        tactic = StrategyTactic.query.get(rec['tactic_id'])
        theme = StrategyTheme(refno=str(rec['theme_refno']),
                    tactic=tactic, content=rec['theme_content'])
        db.session.add(theme)
    db.session.commit()


def load_activities():
    import pandas as pd
    data = pd.read_excel('kpi.xlsx', header=0, sheet_name='activity')
    for idx, rec in data.iterrows():
        theme = StrategyTheme.query.get(rec['theme_id'])
        activity = StrategyActivity(refno=str(rec['activity_refno']),
                    theme=theme, content=rec['activity_content'])
        db.session.add(activity)
    db.session.commit()


from main import db
from models import Student
from pandas import read_excel
def load_students():
    data = read_excel('data/studentListClassOf2560.xlsx', header=None,
        names=['refno', 'uid', 'title', 'firstname', 'lastname'])
    for _, row in data.iterrows():
        student = Student(refno=row['refno'],
                            th_first_name=row['firstname'],
                            th_last_name=row['lastname'],
                            id=row['uid'],
                            title=row['title']
                            )
        db.session.add(student)
    db.session.commit()


from models import Province, District, Subdistrict
def load_provinces():
    data = read_excel('data/tambon.xlsx')
    data['changwat'] = \
        data['CHANGWAT_T'].str.split('.').str.get(1).str.lstrip()
    added_ps = set()
    for _, row in data[['changwat', 'CH_ID']].iterrows():
        if str(row['CH_ID']) not in added_ps:
            p = Province(code=str(row['CH_ID']),
                        name=unicode(row['changwat']))
            db.session.add(p)
            added_ps.add(str(row['CH_ID']))
    db.session.commit()


def load_districts():
    data = read_excel('data/tambon.xlsx')
    data['amphoe'] = \
        data['AMPHOE_T'].str.split('.').str.get(1).str.lstrip()
    added_items = set()
    for _, row in data[['amphoe', 'AM_ID', 'CH_ID']].iterrows():
        if str(row['AM_ID']) not in added_items:
            p = Province.query.filter(
                    Province.code==str(row['CH_ID'])).first()
            d = District(code=str(row['AM_ID']),
                    name=row['amphoe'])
            db.session.add(d)
            added_items.add(str(row['AM_ID']))
            p.districts.append(d)
            db.session.commit()


def load_subdistricts():
    data = read_excel('data/tambon.xlsx')
    data['tambon'] = \
        data['TAMBON_T'].str.split('.').str.get(1).str.lstrip()
    added_items = set()
    for _, row in data[['tambon', 'TA_ID', 'AM_ID']].iterrows():
        if str(row['TA_ID']) not in added_items:
            a = District.query.filter(
                    District.code==str(row['AM_ID'])).first()
            d = Subdistrict(code=str(row['TA_ID']),
                    name=row['tambon'])
            db.session.add(d)
            added_items.add(str(row['TA_ID']))
            a.subdistricts.append(d)
            db.session.commit()
