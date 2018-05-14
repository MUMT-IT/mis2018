from datetime import datetime
from sqlalchemy.sql import select
from flask import request
from flask import jsonify, render_template
from pandas import DataFrame
from collections import defaultdict

from . import kpibp as kpi
from ..main import db, json_keyfile
from ..models import (Org, KPI, Strategy, StrategyTactic,
                      StrategyTheme, StrategyActivity, KPISchema)

import gspread
import sys
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive']

def get_credential(json_keyfile):
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
    return gspread.authorize(credentials)


def convert_python_bool(data, key):
    """Converts Python boolean to Javascript boolean"""

    value = data.get(key, None)
    if value is None:
        return None
    else:
        return 'true' if value else 'false'


@kpi.route('/')
def main():
    orgs = db.session.query(Org)
    return render_template('kpi/main.html', orgs=orgs)


@kpi.route('/strategy/')
def add_strategy():
    orgs_choices = [{'id': o.id, 'name': o.name} for o in
                    db.session.query(Org.id, Org.name)]
    all_strategies = [dict(id=st.id, refno=st.refno, org_id=st.org_id,
                           content=st.content, created_at=st.created_at)
                      for st in db.session.query(Strategy)]
    all_tactics = [dict(id=tc.id, refno=tc.refno, strategy_id=tc.strategy_id,
                        content=tc.content, created_at=tc.created_at)
                   for tc in db.session.query(StrategyTactic)]
    all_themes = [dict(id=th.id, refno=th.refno, tactic_id=th.tactic_id,
                       content=th.content, created_at=th.created_at)
                  for th in db.session.query(StrategyTheme)]
    all_activities = [dict(id=ac.id, refno=ac.refno, theme_id=ac.theme_id,
                           content=ac.content, created_at=ac.created_at)
                      for ac in db.session.query(StrategyActivity)]
    return render_template('/kpi/add_strategy.html',
                           orgs=orgs_choices, strategies=all_strategies,
                           tactics=all_tactics, themes=all_themes,
                           activities=all_activities)


@kpi.route('/edit/<int:kpi_id>', methods=['POST', 'GET'])
def edit(kpi_id):
    if request.method == 'POST':
        kpi_data = request.form
        kpi = KPI.query.get(kpi_id)
        for k in kpi_data:
            if k == 'available':
                available = kpi_data.get(k, None)
                if available == 'true':
                    setattr(kpi, k, True)
                elif available == 'false':
                    setattr(kpi, k, False)
                else:
                    setattr(kpi, k, None)
                continue
            if k == 'frequency':
                frequency = kpi_data.get(k, None)
                if frequency:
                    setattr(kpi, k, int(frequency))
                else:
                    setattr(kpi, k, None)
                continue
            setattr(kpi, k, kpi_data.get(k, None))

        kpi.updated_at = datetime.utcnow()

        db.session.add(kpi)
        db.session.commit()

    kpi = KPI.query.get(kpi_id)
    if not kpi:
        return '<h1>No kpi found</h1>'
    return render_template('/kpi/add.html', kpi=kpi)


@kpi.route('/list/')
def get_kpis():
    kpis = {}
    orgs = Org.query.all()
    for org in orgs:
        kpis[org.name] = []
        for strategy in org.strategies:
            for tactic in strategy.tactics:
                for theme in tactic.themes:
                    for activity in theme.activities:
                        for kpi in activity.kpis:
                            kpis[org.name].append(kpi)
    return render_template('kpi/kpis.html', kpis=kpis)


@kpi.route('/<int:org_id>')
def strategy_index(org_id=1):
    org = db.session.query(Org).get(org_id)
    orgs_choices = [{'id': o.id, 'name': o.name} for o in db.session.query(Org)]

    strategies = []
    for st in db.session.query(Strategy) \
            .filter_by(org_id=org.id):
        strategies.append({'id': st.id, 'refno': st.refno, 'content': st.content})

    tactics = []
    for tc in db.session.query(StrategyTactic):
        tactics.append({'id': tc.id, 'refno': tc.refno,
                        'content': tc.content, 'strategy': tc.strategy_id})

    themes = []
    for th in db.session.query(StrategyTheme):
        themes.append({'id': th.id, 'refno': th.refno,
                       'content': th.content, 'tactic': th.tactic_id})

    activities = []
    for ac in db.session.query(StrategyActivity):
        activities.append({'id': ac.id, 'refno': ac.refno,
                           'content': ac.content, 'theme': ac.theme_id})

    kpi_schema = KPISchema()
    kpis = [kpi_schema.dump(k).data for k in db.session.query(KPI)]
    return render_template('/kpi/strategy_index.html',
                           strategies=strategies,
                           tactics=tactics,
                           themes=themes,
                           activities=activities,
                           org_id=org.id,
                           org_name=org.name,
                           orgs=orgs_choices,
                           kpis=kpis)


@kpi.route('/db')
def test_db():
    users = meta.tables['users']
    s = select([users.c.name])
    data = [rec['name'] for rec in connect.execute(s)]
    return jsonify(data)


@kpi.route('/api/', methods=['POST'])
def add_kpi_json():
    kpi = request.get_json()
    strategy_activity = db.session.query(StrategyActivity).get(kpi['activity_id'])
    newkpi = KPI(name=kpi['name'], created_by=kpi['created_by'])
    strategy_activity.kpis.append(newkpi)
    db.session.add(strategy_activity)
    db.session.commit()
    kpi_schema = KPISchema()
    return jsonify(kpi_schema.dump(newkpi).data)


@kpi.route('/api/edit', methods=['POST'])
def edit_kpi_json():
    kpi_data = request.get_json()
    if not kpi_data['updated_by']:
        # no updater specified
        return jsonify({'response': {'status': 'error'}})

    kpi_data.pop('created_by')
    kpi_data.pop('strategy_activity')
    kpi_data.pop('id')
    k = KPI.query.get(kpi_data['id'])
    for key, value in kpi_data.iteritems():
        setattr(k, key, value)

    # db.session.add(k)
    # db.session.commit()
    return jsonify({'response': {'status': 'success'}})


@kpi.route('/api/strategy', methods=['POST'])
def add_strategy_json():
    new_str = request.get_json()
    strategy = Strategy(refno=new_str['refno'],
                        content=new_str['content'],
                        org_id=int(new_str['org_id']))
    db.session.add(strategy)
    db.session.commit()

    return jsonify(dict(id=strategy.id,
                        refno=strategy.refno,
                        created_at=strategy.created_at,
                        org_id=strategy.org_id,
                        content=strategy.content))


@kpi.route('/api/tactic', methods=['POST'])
def add_tactic_json():
    new_tc = request.get_json()
    tactic = StrategyTactic(
        refno=new_tc['refno'],
        content=new_tc['content'],
        strategy_id=int(new_tc['strategy_id']),
    )
    db.session.add(tactic)
    db.session.commit()

    return jsonify(dict(id=tactic.id,
                        refno=tactic.refno,
                        created_at=tactic.created_at,
                        strategy_id=tactic.strategy_id,
                        content=tactic.content))


@kpi.route('/api/theme', methods=['POST'])
def add_theme_json():
    new_th = request.get_json()
    theme = StrategyTheme(
        refno=new_th['refno'],
        content=new_th['content'],
        tactic_id=int(new_th['tactic_id']),
    )
    db.session.add(theme)
    db.session.commit()

    return jsonify(dict(id=theme.id,
                        refno=theme.refno,
                        created_at=theme.created_at,
                        tactic_id=theme.tactic_id,
                        content=theme.content))


@kpi.route('/api/activity', methods=['POST'])
def add_activity_json():
    new_ac = request.get_json()
    activity = StrategyActivity(
        refno=new_ac['refno'],
        content=new_ac['content'],
        theme_id=int(new_ac['theme_id']),
    )
    db.session.add(activity)
    db.session.commit()
    return jsonify(dict(id=activity.id,
                        refno=activity.refno,
                        created_at=activity.created_at,
                        theme_id=activity.theme_id,
                        content=activity.content))

@kpi.route('/api/education/licenses/<program>')
def get_licenses_data(program):
    if program == 'mt':
        sheetkey = '1Dv9I96T0UUMROSx7hO9u_N7a3lzQ969LiVvL_kBMRqE'
    elif program == 'rt':
        sheetkey = '14iWhBvL2i-nkcB7U8TrfS7YUTErRq1aPtamT3lgePhY'
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetkey).sheet1
    df = DataFrame(wks.get_all_records())
    data = []
    grouped = df.groupby(['graduate', 'apply', 'result']).count()['id']
    for year in grouped.index.levels[0]:
        d = {'year': year}
        d['count'] = defaultdict(dict)
        d['count']['total'] = grouped.xs(year).sum()
        d['count']['applied'] = grouped.xs(year).xs('TRUE').sum()
        d['count']['passed'] = grouped.xs(year).xs('TRUE').xs('TRUE').sum()
        d['percent'] = defaultdict(dict)
        d['percent']['applied'] = d['count']['applied']/float(d['count']['total'])*100.0
        d['percent']['passed'] = d['count']['passed']/float(d['count']['applied'])*100.0
        data.append(d)
    return jsonify(data)