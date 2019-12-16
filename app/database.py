from datetime import datetime
from sqlalchemy.sql import func
from main import db
import pandas as pd
from chemdb.models import ChemItem
from staff.models import StaffAccount, StaffPersonalInfo
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
def load_students(excelfile):
    data = read_excel(excelfile, header=None,
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


def load_chem_items(excel_file):
    if not excel_file:
        return 'No Excel file specified.'

    try:
        df = pd.read_excel(excel_file)
    except:
        return 'Errors occured.'
    else:
        for ix, row in df.iterrows():
            name = row['Name']
            msds = row['MSDS']
            cas = row['CAS']
            company_code = row['Company Code']
            container_size = row['Container size']
            container_unit = row['Container unit']
            vendor = row['Vendors']
            location = row['Location']
            citem = ChemItem(name=name, desc=name,
                             msds=msds, cas=cas,
                             company_code=company_code,
                             container_size=container_size,
                             container_unit=container_unit,
                             vendor=vendor,
                             location=location)
            if (not pd.isna(row['e-mail'])) and ('_at_' in row['e-mail']):
                email, address = row['e-mail'].split('_at_')
                staff = StaffAccount.query.filter_by(email=email).first()
                if staff and row['Name']:
                    citem.contact = staff
            db.session.add(citem)
        db.session.commit()

def load_staff_list(excel_file):
    df = pd.read_excel(excel_file)
    for idx,row in df.iterrows():
        if pd.isna(row['email']):
            continue
        acnt = StaffAccount.query.filter_by(email=row['email']).first()
        if acnt:
            # print('Updating staff...')
            acnt.personal_info.th_firstname = row['th_firstname']
            acnt.personal_info.th_lastname = row['th_lastname']
            acnt.personal_info.org_id = row['org_id']
            acnt.password = str(row['password'])
            acnt.personal_info.org_id = row['org_id']
        else:
            # print('Inserting new staff...')
            personal_info = StaffPersonalInfo(
                th_firstname=row['th_firstname'],
                th_lastname=row['th_lastname'],
                en_firstname=row['en_firstname'].lower().title(),
                en_lastname=row['en_lastname'].lower().title(),
                org_id=row['org_id']
            )
            acnt = StaffAccount(
                email=row['email'],
                personal_info=personal_info,
            )
            acnt.password = str(row['password'])
        # print(u'{} {}'.format(acnt.email, acnt.personal_info.org_id))
        db.session.add(acnt)
    db.session.commit()
