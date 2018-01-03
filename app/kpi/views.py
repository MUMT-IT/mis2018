from datetime import datetime
from sqlalchemy.sql import select
from flask import request
from flask import jsonify, render_template

from . import kpibp as kpi
from ..models import strategies
from .. import meta, connect



@kpi.route('/strategy/')
def add_strategy():
    orgs = meta.tables['orgs']
    s = select([orgs.c.id, orgs.c.name])
    orgs_choices = [{'id': o.id, 'name': o.name} for o in connect.execute(s)]
    strategy_tb = meta.tables['strategies']
    all_strategies = [dict(id=st.id, refno=st.refno, owner=st.owner,
                        content=st.content, created_at=st.created_at)\
                        for st in connect.execute(select([strategy_tb]))]
    tactic_tb = meta.tables['strategy_tactics']
    all_tactics = [dict(id=tc.id, refno=tc.refno, parent=tc.parent,
                        content=tc.content, created_at=tc.created_at)\
                        for tc in connect.execute(select([tactic_tb]))]
    theme_tb = meta.tables['strategy_themes']
    all_themes = [dict(id=th.id, refno=th.refno, parent=th.parent,
                        content=th.content, created_at=th.created_at)\
                        for th in connect.execute(select([theme_tb]))]
    activity_tb = meta.tables['strategy_activities']
    all_activities = [dict(id=ac.id, refno=ac.refno, parent=ac.parent,
                        content=ac.content, created_at=ac.created_at)\
                        for ac in connect.execute(select([activity_tb]))]
    return render_template('/kpi/add_strategy.html',
                orgs=orgs_choices, strategies=all_strategies,
                tactics=all_tactics, themes=all_themes,
                activities=all_activities)


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


@kpi.route('/<int:org_id>')
def index(org_id=1): 
    strategy_table = meta.tables['strategies']
    tactic_table = meta.tables['strategy_tactics']
    theme_table = meta.tables['strategy_themes']
    activity_table = meta.tables['strategy_activities']
    orgs = meta.tables['orgs']
    s = select([orgs.c.id, orgs.c.name]).where(orgs.c.id==org_id)
    org_name = connect.execute(s).fetchone().name

    s = select([strategy_table.c.id,
                strategy_table.c.refno, strategy_table.c.content]).where(strategy_table.c.owner==org_id)
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
                activities=activities,
                org_name=org_name)


@kpi.route('/db')
def test_db():
    users = meta.tables['users']
    s = select([users.c.name])
    data = [rec['name'] for rec in connect.execute(s)]
    return jsonify(data)


@kpi.route('/api/', methods=['POST'])
def add_kpi_json():
    new_kpi = request.get_json()
    new_kpi['created_at'] = datetime.now()
    return jsonify(new_kpi)


@kpi.route('/api/strategy', methods=['POST'])
def add_strategy_json():
    new_str = request.get_json()
    strategies = meta.tables['strategies']
    ins = strategies.insert().values(
        refno=new_str['refno'],
        content=new_str['content'],
        owner=int(new_str['owner']),
    )
    result = connect.execute(ins)
    st = connect.execute(select([strategies]).where(
            strategies.c.id==result.inserted_primary_key[0])).fetchone()
    return jsonify(dict(id=st.id,
                    refno=st.refno,
                    created_at=st.created_at,
                    owner=st.owner,
                    content=st.content))


@kpi.route('/api/tactic', methods=['POST'])
def add_tactic_json():
    new_tc = request.get_json()
    tactic_tb = meta.tables['strategy_tactics']
    ins = tactic_tb.insert().values(
        refno=new_tc['refno'],
        content=new_tc['content'],
        parent=int(new_tc['parent']),
    )
    result = connect.execute(ins)
    tc = connect.execute(select([tactic_tb]).where(
            tactic_tb.c.id==result.inserted_primary_key[0])).fetchone()
    return jsonify(dict(id=tc.id,
                    refno=tc.refno,
                    created_at=tc.created_at,
                    parent=tc.parent,
                    content=tc.content))


@kpi.route('/api/theme', methods=['POST'])
def add_theme_json():
    new_th = request.get_json()
    theme_tb = meta.tables['strategy_themes']
    ins = theme_tb.insert().values(
        refno=new_th['refno'],
        content=new_th['content'],
        parent=int(new_th['parent']),
    )
    result = connect.execute(ins)
    th = connect.execute(select([theme_tb]).where(
            theme_tb.c.id==result.inserted_primary_key[0])).fetchone()
    return jsonify(dict(id=th.id,
                    refno=th.refno,
                    created_at=th.created_at,
                    parent=th.parent,
                    content=th.content))


@kpi.route('/api/activity', methods=['POST'])
def add_activity_json():
    new_ac = request.get_json()
    activity_tb = meta.tables['strategy_activities']
    ins = activity_tb.insert().values(
        refno=new_ac['refno'],
        content=new_ac['content'],
        parent=int(new_ac['parent']),
    )
    result = connect.execute(ins)
    ac = connect.execute(select([activity_tb]).where(
            activity_tb.c.id==result.inserted_primary_key[0])).fetchone()
    return jsonify(dict(id=ac.id,
                    refno=ac.refno,
                    created_at=ac.created_at,
                    parent=ac.parent,
                    content=ac.content))