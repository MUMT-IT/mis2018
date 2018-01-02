from sqlalchemy.sql import select
from flask import jsonify, render_template

from . import kpibp as kpi
from ..models import strategies
from .. import meta, connect


@kpi.route('/add/')
def add():
    orgs = meta.tables['orgs']
    s = select([orgs.c.id, orgs.c.name])
    orgs_choices = [o for o in connect.execute(s)]
    strategies = meta.tables['strategies']
    s = select([strategies.c.id, strategies.c.content])
    strategies = [{'id': st.id, 'content': st.content}
                    for st in connect.execute(s)]
    print(strategies)
    return render_template('/kpi/add.html',
            orgs_choices=orgs_choices,
            strategies=strategies)



@kpi.route('/list/')
def get_kpis():
    return jsonify(strategies)


@kpi.route('/')
def index(): 
    strategy_table = meta.tables['strategies']
    tactic_table = meta.tables['strategy_tactics']
    theme_table = meta.tables['strategy_themes']
    activity_table = meta.tables['strategy_activities']
    s = select([strategy_table.c.id, strategy_table.c.refno, strategy_table.c.content])
    strategies = [
        {'id': st.id, 'refno': st.refno, 'content': st.content} for st in connect.execute(s)
    ]
    s = select([tactic_table.c.id, tactic_table.c.refno,
                    tactic_table.c.content, tactic_table.c.parent])
    tactics = [
        {'id': tc.id, 'refno': tc.refno, 'content': tc.content, 'strategy': tc.parent}\
        for tc in connect.execute(s)
    ]
    s = select([theme_table.c.id, theme_table.c.refno,
                    theme_table.c.content, theme_table.c.parent])
    themes = [
        {'id': th.id, 'refno': th.refno, 'content': th.content, 'tactic': th.parent}\
        for th in connect.execute(s)
    ]
    s = select([activity_table.c.id, activity_table.c.refno,
                    activity_table.c.content, activity_table.c.parent])
    activities = [
        {'id': ac.id, 'refno': ac.refno, 'content': ac.content, 'theme': ac.parent}\
        for ac in connect.execute(s)
    ]
    return render_template('/kpi/index.html',
                strategies=strategies,
                tactics=tactics,
                themes=themes,
                activities=activities)


@kpi.route('/db')
def test_db():
    users = meta.tables['users']
    s = select([users.c.name])
    data = [rec['name'] for rec in connect.execute(s)]
    return jsonify(data)