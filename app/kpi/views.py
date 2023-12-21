from datetime import datetime
from sqlalchemy.sql import select
from flask import request
from flask import jsonify, render_template, Response
from flask_login import login_required
import pandas as pd
from pandas import DataFrame
import numpy as np
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from . import kpibp as kpi
from ..main import db, json_keyfile
from ..models import (Org, KPI, Strategy, StrategyTactic,
                      StrategyTheme, StrategyActivity, KPISchema, Dashboard)

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
    kpi_withdata = defaultdict(int)
    kpi_withoutdata = defaultdict(int)
    total_kpis = 0
    total_kpis_with_data = 0
    total_kpis_without_data = 0
    orgs = Org.query.all()
    labels = []
    for org in orgs:
        kpis[org.name] = []
        for strategy in org.strategies:
            for tactic in strategy.tactics:
                for theme in tactic.themes:
                    for activity in theme.activities:
                        for kpi in activity.kpis:
                            kpis[org.name].append(kpi)
                            total_kpis += 1
                            if kpi.reportlink:
                                total_kpis_with_data += 1
                                kpi_withdata[org.name] += 1
                            else:
                                total_kpis_without_data += 1
                                kpi_withoutdata[org.name] += 1
    for orgname in kpis:
        if kpis[orgname]:
            labels.append(orgname)

    datasets = []
    datasets.append({
        'label': 'With data',
        'data': [kpi_withdata[org] for org in labels]
    })
    datasets.append({
        'label': 'Without data',
        'data': [kpi_withoutdata[org] for org in labels]
    })

    return render_template('kpi/kpis.html',
                           kpis=kpis,
                           datasets=datasets,
                           labels=labels,
                           total_kpis=total_kpis,
                           total_kpis_with_data=total_kpis_with_data,
                           total_kpis_without_data=total_kpis_without_data,
                           total_percents='%.2f%%' % (total_kpis_with_data / float(total_kpis) * 100.0))


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
    kpis = [kpi_schema.dump(k) for k in db.session.query(KPI)]
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
    return jsonify(kpi_schema.dump(newkpi))


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
        d['percent']['applied'] = d['count']['applied'] / float(d['count']['total']) * 100.0
        d['percent']['passed'] = d['count']['passed'] / float(d['count']['applied']) * 100.0
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
        'ethic': range(21, 28),
        'knowledge': range(28, 35),
        'wisdom': range(35, 40),
        'relationship skill': range(40, 46),
        'analytical skill': range(46, 51),
        'professional skill': range(51, 56)
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


@kpi.route('/api/hr/r2r')
def get_r2r_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1c7eE-kMre6BeBac_JphTcJZtO4Qi9x6_UAAivtr2NNs').sheet1
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


@kpi.route('/hr/r2r')
def show_r2r():
    return render_template('hr/r2r.html')


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


@kpi.route('/api/service/eqasamples')
def get_eqasamples_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1uSiEM5Wky-ezL3YnXUp-BT6JPAin8zRq-JK8DRW57no').sheet1
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


@kpi.route('/service/eqasamples')
def show_eqasamples():
    return render_template('service/eqasamples.html')


@kpi.route('/api/service/eqasatisfaction')
def get_eqasatisfaction_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1rBIrsFtRiC1Jk-KQkAhFyCAAl-e4M_jFYqNCKAp3ePo').sheet1
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


@kpi.route('/service/eqasatisfaction')
def show_eqasatisfaction():
    return render_template('service/eqasatisfaction.html')


@kpi.route('/api/service/labqa')
def get_labqa_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('11C8IGLnK8KB_lqxRCvP_yn66jiQ04ksCwwiqT2sK87c').sheet1
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
            'lab': row['lab'],
            'data': pairs
        })
    return jsonify(data)


@kpi.route('/service/labqa')
def show_labqa():
    return render_template('service/labqa.html')


@kpi.route('/api/service/labcustomer')
def get_labcustomer_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1z39CHLaVSne2oRFPQ2ivG1LRz6ilWeGcLB_1A6u__4I').sheet1
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


@kpi.route('/service/labcustomer')
def show_labcustomer():
    return render_template('service/labcustomer.html')


@kpi.route('/api/service/labvisitor')
def get_labvisitor_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1snygUOC8ZgqAobi14qu8d12vrYbjZCcWuduHEm0kgQY').sheet1
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


@kpi.route('/service/labvisitor')
def show_labvisitor():
    return render_template('service/labvisitor.html')


@kpi.route('/api/service/labkpi')
def get_labkpi_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1WVThT8oc7FlPMp59EzqaSs2jywZ4-WIdanWnAytIJE8').sheet1
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


@kpi.route('/service/labkpi')
def show_labkpi():
    return render_template('service/labkpi.html')


@kpi.route('/api/service/labcustomer_relation')
def get_labcustomer_relation_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1LLIozfr_pziIWe6HO-ix4j-6oelunEpL3CO8suBaavc').sheet1
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


@kpi.route('/service/labcustomer_relation')
def show_labcustomer_relation():
    return render_template('service/labcustomer_relation.html')


@kpi.route('/api/service/labregulars')
def get_labregulars_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1TkjpzK3yeTytFZ4jQvGbQT2ftSAlnmi16b0ytV75nWU').sheet1
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


@kpi.route('/service/labregulars')
def show_labregulars():
    return render_template('service/labregulars.html')


@kpi.route('/api/service/labawareness')
def get_labawareness_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1lCSR_dnfKah_taAxVNfkjVEmUPDrpQEgf36hfJ5eyc8').sheet1
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


@kpi.route('/service/labawareness')
def show_labawareness():
    return render_template('service/labawareness.html')


@kpi.route('/api/service/labmedia')
def get_labmedia_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1J8XwgKWreRf3p7yfjVTdKDfFKPNLyb3uWA8CmjMXtg4').sheet1
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


@kpi.route('/service/labmedia')
def show_labmedia():
    return render_template('service/labmedia.html')


@kpi.route('/api/service/labmarket_share')
def get_labmarket_share_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1_TQb5YkYcGv230CnRiJ_-KYZYBFNr6TmKgbk6_aDCrA').sheet1
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


@kpi.route('/service/labmarket_share')
def show_labmarket_share():
    return render_template('service/labmarket_share.html')


@kpi.route('/api/management/governance')
def get_governance_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1qZOhp8u5LBObm4V4MQc3IESOcBoPT4HOMc9TjexxZaU').sheet1
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


@kpi.route('/management/governance')
def show_governance():
    return render_template('management/governance.html')


@kpi.route('/api/management/vmv')
def get_vmv_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1AeA3_5NdzbIReFDKhG9oVUPxJ1h1FosczzZHYRTRF3w').sheet1
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


@kpi.route('/management/vmv')
def show_vmv():
    return render_template('management/vmv.html')


@kpi.route('/api/management/admin_process')
def get_admin_process_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1B8d42jKLpfRGBJm8wWuT0vQ6W_VXm4rR4SofE7Uj-bc').sheet1
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


@kpi.route('/management/admin_process')
def show_admin_process():
    return render_template('management/admin_process.html')


@kpi.route('/api/management/it')
def get_it_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1J6Qo2q7ncmwV01O3rUv9Mx_LHf_tQONFDean0dU-2xo').sheet1
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


@kpi.route('/management/it')
def show_it():
    return render_template('management/it.html')


@kpi.route('/api/edu/channel')
def get_channel_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1bMQyohkuRr3lLVTdvbg90lXzqsYMoQbNtSZ6QssBzqY').sheet1
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


@kpi.route('/edu/channel')
def show_channel():
    return render_template('edu/channel.html')


@kpi.route('/api/edu/recruitment')
def get_recruitment_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('113U1wDDqhxjG0AIuQKOtbOANiI-cZSpm_JXKNVjTatE').sheet1
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


@kpi.route('/edu/recruitment')
def show_recruitment():
    return render_template('edu/recruitment.html')


@kpi.route('/api/edu/mt_recognition')
def get_mt_recognition_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1u_-4_0yaPoBaDpAh3c69cypm7GzTiQzUXC5dkq7l2MU').sheet1
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


@kpi.route('/edu/mt_recognition')
def show_mt_recognition():
    return render_template('edu/mt_recognition.html')


@kpi.route('/api/edu/application_ratio')
def get_application_ratio_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1gKIOrqAnRAqK_E661aTtvMnEUSiEWr8wokuSHOnczl0').sheet1
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


@kpi.route('/edu/application_ratio')
def show_application_ratio():
    return render_template('edu/application_ratio.html')


@kpi.route('/api/edu/employer_satisfaction')
def get_employer_satisfaction_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1YNks85qtUSYvn_6urR36ONKXU8Vxut_Vqie2oCV3E2A').sheet1
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


@kpi.route('/edu/employer_satisfaction')
def show_employer_satisfaction():
    return render_template('edu/employer_satisfaction.html')


@kpi.route('/api/edu/graduation_rate')
def get_graduation_rate_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1BpVYxgQ6rADEo9Om6rNsOOBBl34rUSp4k_egLBH0r3M').sheet1
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


@kpi.route('/edu/graduation_rate')
def show_graduation_rate():
    return render_template('edu/graduation_rate.html')


@kpi.route('/api/edu/fclub')
def get_fclub_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1PjbLjZFkHstBOA2AtgGo8QhLf4-EaShFcL1orE_rXrw').sheet1
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


@kpi.route('/edu/fclub')
def show_fclub():
    return render_template('edu/fclub.html')


@kpi.route('/api/edu/market_share')
def get_market_share_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1NIbyVXgfTKlihxxfF4vsNKU20v-EmXC8dzRSQOZbbr4').sheet1
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


@kpi.route('/edu/market_share')
def show_market_share():
    return render_template('edu/market_share.html')


@kpi.route('/api/edu/ent_comp')
def get_ent_comp_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1sDrJxBoraNbWYqdtiqQDnNlZHXv7yVVADw2iCb66JqQ').sheet1
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


@kpi.route('/edu/ent_comp')
def show_ent_comp():
    return render_template('edu/ent_comp.html')


@kpi.route('/api/edu/env_course')
def get_env_course_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1besmOStEJIe03jBFelDlCYV-lvM66fNU7mBxLE-eHQo').sheet1
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


@kpi.route('/edu/env_course')
def show_env_course():
    return render_template('edu/env_course.html')


@kpi.route('/api/edu/customer_vmv')
def get_customer_vmv_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1OgqhAVoqf28JOAFEFcrCoUFyAt0HbWQM-zzPqdP0-oA').sheet1
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


@kpi.route('/edu/customer_vmv')
def show_customer_vmv():
    return render_template('edu/customer_vmv.html')


@kpi.route('/api/edu/faculty_bond')
def get_faculty_bond_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1WUQelJaV3vlHX3oBqxa-vZbFB0B1JGyfGIH6A-t75cQ').sheet1
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


@kpi.route('/edu/faculty_bond')
def show_faculty_bond():
    return render_template('edu/faculty_bond.html')


@kpi.route('/api/edu/newcomers')
def get_newcomers_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1Hko59C27ukCh8eHk7SYlKNfUegCm5XRWFtzdG8yRL6A').sheet1
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


@kpi.route('/edu/newcomers')
def show_newcomers():
    return render_template('edu/newcomers.html')


@kpi.route('/api/edu/gradstud_comp')
def get_gradstud_comp_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1m_T5MxgMr5_VVNia-FeE6ughwg5Jb5Q2wa0qJbgtO8o').sheet1
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


@kpi.route('/edu/gradstud_comp')
def show_gradstud_comp():
    return render_template('edu/gradstud_comp.html')


@kpi.route('/api/edu/scholarship')
def get_scholarship_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1J9R0hYYe6SZ173qSjn_2CJWf-zaNapytypmyydZGR8o').sheet1
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


@kpi.route('/edu/scholarship')
def show_scholarship():
    return render_template('edu/scholarship.html')


@kpi.route('/api/edu/scholarship_rate')
def get_scholarship_rate_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1L4kkAEIpxcbXwsyyMqfAGOlXwt0PG5Su9kdPLxP5W4o').sheet1
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


@kpi.route('/edu/scholarship_rate')
def show_scholarship_rate():
    return render_template('edu/scholarship_rate.html')


@kpi.route('/api/edu/grad_eval_internal')
def get_grad_eval_internal_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1871BjZ2FiZE0gQmXtxEG4Von5b7E9gHq_qzfd5z7rXM').sheet1
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


@kpi.route('/edu/grad_eval_internal')
def show_grad_eval_internal():
    return render_template('edu/grad_eval_internal.html')


@kpi.route('/api/edu/grad_eval_external')
def get_grad_eval_external_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('15Wg6T4ZVrPFndJXfkj9Nck4bBuXmvuEkubW6dDvk4MU').sheet1
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


@kpi.route('/edu/grad_eval_external')
def show_grad_eval_external():
    return render_template('edu/grad_eval_external.html')


@kpi.route('/api/management/boardeval')
def get_boardeval_data():
    gc = get_credential(json_keyfile)
    sheet = gc.open_by_key('1bv-R4JIXUMJShS4JooQhe6749pVz0mY0z7yAk2NJ0fk').sheet1
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


@kpi.route('/management/boardeval')
def show_boardeval():
    return render_template('management/boardeval.html')


@kpi.route('/dashboard')
@login_required
def dashboard_index():
    dashboard = Dashboard.query.all()
    return render_template('kpi/dashboard/index.html', dashboard=dashboard)
