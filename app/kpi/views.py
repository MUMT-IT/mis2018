from datetime import datetime
from sqlalchemy.sql import select
from flask import request
from flask import jsonify, render_template, Response
import pandas as pd
from pandas import DataFrame
import numpy as np
from collections import defaultdict
from dateutil.relativedelta import relativedelta

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

@kpi.route('/api/edu/licenses/<program>')
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


@kpi.route('/edu/licenses/')
def show_licenses():
    return render_template('edu/licenses.html')


@kpi.route('/api/edu/duration')
def get_duration_data():
    gc = get_credential(json_keyfile)
    sheetkey = '1aZf6-072bIh33Tl5dSTVk8LQt8Yzkk_Fx7hYYgUBQas'
    wks = gc.open_by_key(sheetkey).sheet1
    df = DataFrame(wks.get_all_records())
    start_date = df.columns[12]
    end_date = df.columns[11]
    df[start_date] = pd.to_datetime(df[start_date])
    df[end_date] = pd.to_datetime(df[end_date])
    df['totaldays'] = (df[end_date] - df[start_date]).dt.days
    grouped = df.groupby([df.columns[14], df.columns[9], df.columns[6]]).mean()
    data = []
    for program in grouped.index.levels[0]:
        for degree in grouped.index.levels[1]:
            for year in grouped.index.levels[2]:
                try:
                    d = {
                        'program': program,
                        'degree': degree,
                        'year': year,
                        'avgdays': grouped.xs(program).xs(degree).xs(year)['totaldays']
                    }
                except KeyError:
                    d = {
                        'program': program,
                        'degree': degree,
                        'year': year,
                        'avgdays': None
                    }
                data.append(d)
    return jsonify(data)


@kpi.route('/edu/duration/')
def show_duration():
    return render_template('edu/duration.html')


@kpi.route('/api/edu/evaluation')
def get_evaluation_data():
    sheets = [
        {
            'program': 'MT',
            'year': 2556,
            'sheetkey': '1g7cXTRWxKY0ZEolbHt2SWX-R9xvQUbp91-04I04kR3Y'
        },
        {
            'program': 'MT',
            'year': 2557,
            'sheetkey': '18H3N82WY_gshdBMGo68i5_xrrcBaYidf6TPfKp9ApjU'
        },
        {
            'program': 'RT',
            'year': 2556,
            'sheetkey': '1O9OV9ee4bNLb1l3HV7Xg6Ek4uePZg1uWTMa8UCgfGXc'
        },
        {
            'program': 'RT',
            'year': 2557,
            'sheetkey': '1ce5mcOeIxdYVWbVJATKS7r3F1FvRQ2kX1dPVbC127ls'
        }
    ]

    columns = {
        'ethic': range(21,28),
        'knowledge': range(28, 35),
        'wisdom': range(35,40),
        'relationship skill': range(40,46),
        'analytical skill': range(46,51),
        'professional skill': range(51,56)
    }
    gc = get_credential(json_keyfile)
    data = []
    for item in sheets:
        bags = []
        worksheet = gc.open_by_key(item['sheetkey'])
        wks = worksheet.sheet1
        values = wks.get_all_values()
        df = DataFrame(values[1:], columns=values[0])
        for topic in columns:
            scores = []
            for col in df.columns[columns[topic]]:
                temp = []
                for v in df[col]:
                    try:
                        v = float(v)
                    except:
                        continue
                    else:
                        temp.append(v)
                if temp:
                    scores.append(np.mean(temp))
            avgscores = np.mean(scores)
            if np.isnan(avgscores):
                avgscores = None
            bags.append({
                'program': item['program'],
                'topic': topic,
                'score': avgscores
            })
        data.append({
            'year': item['year'],
            'program': item['program'],
            'data': bags
        })
    return jsonify(data)


@kpi.route('/edu/evaluation/wrs')
def show_wrs():
    return render_template('edu/wrs.html')


@kpi.route('/api/edu/evaluation/wrs')
def get_wrs_data():
    sheets = [
        {
            'program': 'MT',
            'year': 2556,
            'sheetkey': '1g7cXTRWxKY0ZEolbHt2SWX-R9xvQUbp91-04I04kR3Y'
        },
        {
            'program': 'MT',
            'year': 2557,
            'sheetkey': '18H3N82WY_gshdBMGo68i5_xrrcBaYidf6TPfKp9ApjU'
        },
        {
            'program': 'RT',
            'year': 2556,
            'sheetkey': '1O9OV9ee4bNLb1l3HV7Xg6Ek4uePZg1uWTMa8UCgfGXc'
        },
        {
            'program': 'RT',
            'year': 2557,
            'sheetkey': '1ce5mcOeIxdYVWbVJATKS7r3F1FvRQ2kX1dPVbC127ls'
        }
    ]

    columns = {
        'knowledge': 64,
        'professional skill': 65,
        'analytical skill': 66,
        'creativity': 67,
        'team working': 68,
        'social responsibility': 69
    }
    gc = get_credential(json_keyfile)
    data = []
    for item in sheets:
        bags = []
        worksheet = gc.open_by_key(item['sheetkey'])
        wks = worksheet.sheet1
        values = wks.get_all_values()
        df = DataFrame(values[1:], columns=values[0])
        for topic in columns:
            col = df.columns[columns[topic]]
            temp = []
            for v in df[col]:
                try:
                    v = float(v)
                except:
                    continue
                else:
                    temp.append(v)
            if temp:
                avgscores = np.mean(temp)
            if np.isnan(avgscores):
                avgscores = None
            bags.append({
                'topic': topic,
                'score': avgscores
            })
        data.append({
            'year': item['year'],
            'program': item['program'],
            'data': bags
        })
    return jsonify(data)


@kpi.route('/edu/evaluation')
def show_evaluation():
    return render_template('edu/evaluation.html')


@kpi.route('/api/hr/healthstatus')
def get_healthstatus_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1IfLMh6367NCd3MKJ3Py_77DQ4iU_yC5czhm7Px8H5do').sheet1
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


@kpi.route('/hr/healthstatus')
def show_healthstatus():
    return render_template('hr/healthstatus.html')


@kpi.route('/api/hr/perkeval')
def get_perkeval_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1U9hFIoWUm6b_FiyqBxP-aClJCYJDClqhwNmwBDThIIk').sheet1
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


@kpi.route('/hr/perkeval')
def show_perkeval():
    return render_template('hr/perkeval.html')


@kpi.route('/api/hr/firedrill')
def get_firedrill_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1wMw3Mx6uHTVsoCsGpzdS5nT2qoMZSX6RIx3MOPXFq7o').sheet1
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


@kpi.route('/hr/firedrill')
def show_firedrill():
    return render_template('hr/firedrill.html')


@kpi.route('/api/hr/bottle')
def get_bottle_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1lIuFvky6IPJXzEbZ7N-TKcW0v8-O6wV2ckKI0vz3li8').sheet1
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


@kpi.route('/hr/bottle')
def show_bottle():
    return render_template('hr/bottle.html')


@kpi.route('/api/hr/happinometer')
def get_happinometer_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('10_rPtntPyv3qpPvjxkpymdMbjQn7-YusrALlUMqvUCY').sheet1
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


@kpi.route('/hr/happinometer')
def show_happinometer():
    return render_template('hr/happinometer.html')


@kpi.route('/api/hr/personneldevel')
def get_personneldevel_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1N6sRAleoSqcijiq3dhOJhzFO0crcUiStI--MbRS_28I').sheet1
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


@kpi.route('/hr/personneldevel')
def show_personneldevel():
    return render_template('hr/personneldevel.html')


@kpi.route('/api/hr/personneldevel_budget')
def get_personneldevel_budget_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1RYP1clCM6UBukfCpofR3dMPSZr6fM0qbusD4w14Al6U').sheet1
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


@kpi.route('/hr/personneldevel_budget')
def show_personneldevel_budget():
    return render_template('hr/personneldevel_budget.html')


@kpi.route('/api/hr/retention')
def get_retention_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('19odyyAEfO4qMvSVTcCHN9l1-Ax_535oSN4uukhaQ1fk').sheet1
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


@kpi.route('/hr/retention')
def show_retention_budget():
    return render_template('hr/retention.html')


@kpi.route('/api/hr/connection')
def get_connection_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1CogXDN8CdYOWR7tdsOCxqCHaN-5M5lSlub_tF-DiSdA').sheet1
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


@kpi.route('/hr/connection')
def show_connection_budget():
    return render_template('hr/connection.html')


@kpi.route('/api/hr/environ')
def get_environ_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1FfUEC_Nh5L2qBy7QXKxF8JwgMOjv1r0RZOd6rNykNi4').sheet1
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


@kpi.route('/hr/environ')
def show_environ_budget():
    return render_template('hr/environ.html')


@kpi.route('/api/hr/laws')
def get_laws_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1UDCW_ZLgqVzSwgVWTtwq3j8m9lVOjbq2W3Ycls-b1XA').sheet1
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


@kpi.route('/hr/laws')
def show_laws():
    return render_template('hr/laws.html')


@kpi.route('/api/hr/electricity')
def get_electricity_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1y2OxWLdqZyJbueHvXryOq3ns_7vdCd4yv-CdMa1fIDU').sheet1
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


@kpi.route('/hr/electricity')
def show_electricity():
    return render_template('hr/electricity.html')


@kpi.route('/api/hr/awards')
def get_awards_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1_0KbANJv5l2crAIJxejE7N44F2htyWQ9XayPnB6kIqg').sheet1
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


@kpi.route('/hr/awards')
def show_awards():
    return render_template('hr/awards.html')


@kpi.route('/api/service/eqamembers')
def get_eqamembers_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1buFXMoOkfjQZnnJXWbAec0hX8aWkW-oOY-DW53puJVo').sheet1
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


@kpi.route('/service/eqamembers')
def show_eqamembers():
    return render_template('service/eqamembers.html')