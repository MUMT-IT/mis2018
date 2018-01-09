from datetime import datetime
from sqlalchemy.sql import func
from main import db
from models import Org

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


from main import db
from models import Student
from pandas import read_excel
def load_students():
    data = read_excel('studentListClassOf2560.xlsx', header=None,
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