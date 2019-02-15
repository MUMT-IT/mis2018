from flask import render_template
from . import chemdbbp as chemdb
from models import ChemItem


@chemdb.route('/')
def index():
    items = ChemItem.query.all()
    return render_template('chemdb/index.html', items=items)
