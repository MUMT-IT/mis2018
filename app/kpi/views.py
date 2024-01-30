import json
from datetime import datetime

import arrow
from flask_wtf.csrf import generate_csrf
from pytz import timezone
from sqlalchemy.sql import select
from flask import request, make_response, url_for, flash
from flask import jsonify, render_template, Response
from flask_login import login_required, current_user
import pandas as pd
from pandas import DataFrame
import numpy as np
from collections import defaultdict

from . import kpibp as kpi
from .forms import StrategyForm, StrategyTacticForm, StrategyThemeForm, StrategyActivityForm
from ..data_blueprint.forms import KPIForm, KPIModalForm
from ..main import db, json_keyfile
from ..models import (Org, KPI, Strategy, StrategyTactic,
                      StrategyTheme, StrategyActivity, KPISchema, Dashboard)

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from ..staff.models import StaffPersonalInfo, StaffAccount

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


@kpi.route('/orgs/<int:org_id>/strategy/', methods=['GET', 'POST'])
@kpi.route('/<int:org_id>/strategy/<int:strategy_id>', methods=['GET', 'POST', 'DELETE'])
@login_required
def edit_strategy(org_id, strategy_id=None):
    if strategy_id:
        strategy = Strategy.query.get(strategy_id)
        if request.method == 'DELETE':
            db.session.delete(strategy)
            db.session.commit()
            flash('ลบข้อมูลเรียบร้อยแล้ว', 'success')
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index', org_id=org_id)
            return resp
        form = StrategyForm(obj=strategy)
    else:
        form = StrategyForm()

    if form.validate_on_submit():
        if strategy_id:
            form.populate_obj(strategy)
        else:
            strategy = Strategy()
            form.populate_obj(strategy)
            strategy.org_id = org_id
        db.session.add(strategy)
        db.session.commit()
        flash('บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index', org_id=org_id)
        return resp

    return render_template('/kpi/partials/edit_strategy_form.html',
                           form=form, org_id=org_id, strategy_id=strategy_id)


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


@kpi.route('/orgs/strategies')
@kpi.route('/orgs/<int:org_id>/strategies')
def strategy_index(org_id=None):
    trigger = request.args.get('trigger')
    org = Org.query.get(org_id) if org_id else Org.query.first()
    orgs = Org.query.all()
    return render_template('/kpi/strategy_index.html',
                           org_id=org.id,
                           org_name=org.name,
                           orgs=orgs,
                           trigger=trigger)


@kpi.route('/api/orgs/strategies', methods=['POST'])
@kpi.route('/api/orgs/<int:org_id>/strategies', methods=['GET'])
@login_required
def get_strategies(org_id=None):
    if request.method == 'POST':
        form = request.form
        org_id = form.get('org')
    current_item = request.headers.get('HX-Trigger')
    org = Org.query.get(org_id)
    strategies = org.strategies
    tactics = []
    themes = []
    activities = []
    tactic_id = None
    theme_id = None
    activity_id = None
    strategy_id = None
    if current_item:
        _el, _id = current_item.split('-')
        if _el == 'strategy':
            strategy_id = int(_id)
            curr_st = Strategy.query.get(strategy_id)
            tactics = curr_st.tactics
            tactic_id = tactics[0].id if tactics else None
        elif _el == 'tactic':
            tactic = StrategyTactic.query.get(int(_id))
            strategy_id = tactic.strategy_id
            tactic_id = tactic.id
            tactics = tactic.strategy.tactics
            themes = tactic.themes
            theme_id = themes[0].id if tactic.themes else None
        elif _el == 'theme':
            theme = StrategyTheme.query.get(int(_id))
            tactic = theme.tactic
            tactic_id = tactic.id
            strategy = tactic.strategy
            strategy_id = strategy.id
            tactics = strategy.tactics
            themes = tactic.themes
            theme_id = theme.id
            activities = theme.activities
        elif _el == 'activity':
            activity = StrategyActivity.query.get(int(_id))
            activity_id = activity.id
            theme = activity.theme
            theme_id = theme.id
            activities = theme.activities
            tactic = theme.tactic
            themes = tactic.themes
            tactic_id = tactic.id
            strategy = tactic.strategy
            strategy_id = strategy.id
            tactics = strategy.tactics
    template = render_template('kpi/partials/strategies.html',
                               org_id=org_id,
                               strategies=strategies,
                               strategy_id=strategy_id,
                               tactics=tactics,
                               tactic_id=tactic_id,
                               themes=themes,
                               theme_id=theme_id,
                               activities=activities,
                               activity_id=activity_id,
                               current_item=current_item or '',
                               )
    resp = make_response(template)
    if current_item:
        resp.headers['HX-Trigger-After-Swap'] = json.dumps(
            {"loadKPIs": {"current_item": current_item, "org_id": org_id}})
    if request.method == 'POST':
        resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index', org_id=org_id, _method='GET')
    return resp


@kpi.route('/db')
def test_db():
    users = meta.tables['users']
    s = select([users.c.name])
    data = [rec['name'] for rec in connect.execute(s)]
    return jsonify(data)


@kpi.route('/api/', methods=['POST'])
def add_kpi():
    form = request.form
    current_item = form.get('current_item')
    org_id = form.get('org_id')
    if not current_item:
        resp = make_response()
        resp.headers['HX-Swap'] = 'false'
        return resp, 400

    _el, _id = current_item.split('-')
    items = {
        'strategy': Strategy,
        # 'theme': StrategyTheme,
        # 'tactic': StrategyTactic,
        'activity': StrategyActivity,
    }
    if _el in items:
        item = items[_el].query.get(int(_id))

        kpi = KPI(name=form.get('kpi_name'), created_by=current_user.email)
        item.kpis.append(kpi)
        db.session.add(item)
        db.session.commit()
    resp = make_response()
    resp.headers['HX-Swap'] = 'false'
    resp.headers['HX-Trigger'] = json.dumps({"loadKPIs": {"current_item": current_item, "org_id": org_id}})
    return resp


@kpi.route('/api/orgs/<int:org_id>/kpis/<current_item>')
@login_required
def get_item_kpis(org_id, current_item):
    _el, _id = current_item.split('-')
    items = {
        'strategy': Strategy,
        'theme': StrategyTheme,
        'tactic': StrategyTactic,
        'activity': StrategyActivity,
    }
    labels = {
        'strategy': 'ยุทธศาสตร์',
        'activity': 'กิจกรรม/โครงการ',
        'theme': 'มาตรการ',
        'tactic': 'แผนกลยุทธ์'
    }
    kpis = ''
    item = items[_el].query.get(int(_id))
    title = f'{labels[_el]} {item}'
    if _el in items:
        if hasattr(item, 'kpis'):
            for n, k in enumerate(item.kpis, start=1):
                if k.active:
                    kpi_edit_url = url_for('kpi_blueprint.edit_kpi', kpi_id=k.id)
                    created_at = arrow.get(k.created_at.astimezone(timezone('Asia/Bangkok'))).humanize()
                    kpis += f'''<tr>
                                    <td>{n}</td>
                                    <td>{k.refno or ""}</td>
                                    <td>{k.name}</td>
                                    <td>{created_at}</td>
                                    <td>
                                        <a hx-get="{kpi_edit_url}" hx-target="#kpi-form" hx-swap="innerHTML">
                                        <span class="icon">
                                            <i class="fa-solid fa-pencil"></i>
                                        </span>
                                        </a>
                                    </td>
                                </tr>
                                '''
        else:
            kpis += f'<tr><td colspan=4>ยังไม่สามารถเพิ่มตัวชี้วัดในส่วนนี้ได้</td></tr>'

    edit_url = None
    if _el == 'strategy':
        edit_url = url_for('kpi_blueprint.edit_strategy', strategy_id=item.id, org_id=org_id)
    elif _el == 'tactic':
        edit_url = url_for('kpi_blueprint.edit_tactic', tactic_id=item.id, org_id=org_id)
    elif _el == 'theme':
        edit_url = url_for('kpi_blueprint.edit_theme', theme_id=item.id, org_id=org_id)
    elif _el == 'activity':
        edit_url = url_for('kpi_blueprint.edit_activity', activity_id=item.id, org_id=org_id)

    template = f'''
        <h1 class="title is-size-5">ตัวชี้วัดสำหรับ {title}
            <a hx-get="{edit_url}" hx-target="#item-form" hx-swap="innerHTML">
                <span class="icon">
                    <i class="fa-solid fa-pencil"></i>
                </span>
            </a>
            <a hx-headers='{{"X-CSRF-Token": "{generate_csrf()}"}}' hx-confirm="Are you sure?" hx-delete="{edit_url}" hx-target="#item-form" hx-swap="innerHTML">
                <span class="icon">
                    <i class="fa-solid fa-trash-can has-text-danger"></i>
                </span>
            </a>
        </h1>
        <table class="table is-striped">
            <thead>
            <tr>
                <th>ลำดับที่</th>
                <th>รหัส</th>
                <th>ชื่อตัวชี้วัด</th>
                <th>เพิ่มเมื่อ</th>
                <th></th>
            </tr>
            </thead>
            <tbody>
            {kpis}
            </tbody>
        </table>
    '''
    resp = make_response(template)
    return resp


@kpi.route('/api/kpis/<int:kpi_id>/edit', methods=['GET', 'POST'])
def edit_kpi(kpi_id):
    kpi = KPI.query.get(kpi_id)
    form = KPIModalForm(obj=kpi)
    if form.validate_on_submit():
        print('**', form.account.data, form.keeper.data)
        form.populate_obj(kpi)
        db.session.add(kpi)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Trigger'] = json.dumps({"closeModal": "", "successAlert": "บันทึกข้อมูลแล้ว"})
        return resp
    else:
        print(form.errors)

    return render_template('kpi/partials/kpi_form_modal.html', form=form, kpi_id=kpi_id)


@kpi.route('/orgs/<int:org_id>/strategies/<int:strategy_id>/tactics', methods=['GET', 'POST'])
@kpi.route('/orgs/<int:org_id>/tactics/<int:tactic_id>', methods=['GET', 'POST', 'DELETE'])
@login_required
def edit_tactic(org_id, strategy_id=None, tactic_id=None):
    if tactic_id:
        tactic = StrategyTactic.query.get(tactic_id)
        if request.method == 'DELETE':
            strategy_id = tactic.strategy_id
            db.session.delete(tactic)
            db.session.commit()
            flash('ลบข้อมูลเรียบร้อยแล้ว', 'success')
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index',
                                                  org_id=org_id, trigger=f'strategy-{strategy_id}')
            return resp
        form = StrategyTacticForm(obj=tactic)
    else:
        form = StrategyTacticForm()

    if form.validate_on_submit():
        if tactic_id:
            form.populate_obj(tactic)
        else:
            tactic = StrategyTactic()
            form.populate_obj(tactic)
            tactic.strategy_id = strategy_id
        db.session.add(tactic)
        db.session.commit()
        flash('บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index',
                                              org_id=org_id,
                                              trigger=f'strategy-{strategy_id}')
        return resp
    return render_template('/kpi/partials/edit_strategy_tactic_form.html',
                           form=form,
                           org_id=org_id,
                           strategy_id=strategy_id,
                           tactic_id=tactic_id)


@kpi.route('/orgs/<int:org_id>/tactics/<int:tactic_id>/themes', methods=['GET', 'POST'])
@kpi.route('/orgs/<int:org_id>/themes/<int:theme_id>', methods=['GET', 'POST', 'DELETE'])
def edit_theme(org_id, tactic_id=None, theme_id=None):
    if theme_id:
        theme = StrategyTheme.query.get(theme_id)
        if request.method == 'DELETE':
            tactic_id = theme.tactic_id
            db.session.delete(theme)
            db.session.commit()
            flash('ลบข้อมูลเรียบร้อยแล้ว', 'success')
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index',
                                                  org_id=org_id, trigger=f'tactic-{tactic_id}')
            return resp
        form = StrategyThemeForm(obj=theme)
    else:
        form = StrategyThemeForm()

    if form.validate_on_submit():
        if theme_id:
            form.populate_obj(theme)
        else:
            theme = StrategyTheme()
            form.populate_obj(theme)
            theme.tactic_id = tactic_id
        db.session.add(theme)
        db.session.commit()
        flash('บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index',
                                              org_id=org_id,
                                              trigger=f'tactic-{tactic_id}')
        return resp
    return render_template('/kpi/partials/edit_strategy_theme_form.html',
                           form=form,
                           org_id=org_id,
                           theme_id=theme_id,
                           tactic_id=tactic_id)


@kpi.route('/api/orgs/<int:org_id>/themes/<int:theme_id>/activities', methods=['GET', 'POST'])
@kpi.route('/api/orgs/<int:org_id>/activities/<int:activity_id>', methods=['GET', 'POST', 'DELETE'])
def edit_activity(org_id, theme_id=None, activity_id=None):
    if activity_id:
        activity = StrategyActivity.query.get(activity_id)
        if request.method == 'DELETE':
            theme_id = activity.theme_id
            db.session.delete(activity)
            db.session.commit()
            flash('ลบข้อมูลเรียบร้อยแล้ว', 'success')
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index',
                                                  org_id=org_id, trigger=f'theme-{theme_id}')
            return resp
        form = StrategyActivityForm(obj=activity)
    else:
        form = StrategyActivityForm()

    if form.validate_on_submit():
        if activity_id:
            form.populate_obj(activity)
        else:
            activity = StrategyActivity()
            form.populate_obj(activity)
            activity.theme_id = theme_id
        db.session.add(activity)
        db.session.commit()
        flash('บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Redirect'] = url_for('kpi_blueprint.strategy_index',
                                              org_id=org_id, trigger=f'theme-{theme_id}')
        return resp
    return render_template('/kpi/partials/edit_strategy_activity_form.html',
                           form=form,
                           org_id=org_id,
                           theme_id=theme_id,
                           activity_id=activity_id)


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
