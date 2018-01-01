from sqlalchemy.sql import select
from flask import jsonify, render_template

from . import kpibp as kpi
from ..models import strategies
from .. import meta, connect


@kpi.route('/list/')
def get_kpis():
    return jsonify(strategies)


@kpi.route('/')
def index(): 
    return render_template('/kpi/index.html')


@kpi.route('/db')
def test_db():
    users = meta.tables['users']
    s = select([users.c.name])
    data = [rec['name'] for rec in connect.execute(s)]
    return jsonify(data)