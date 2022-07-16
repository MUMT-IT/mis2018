# -*- coding:utf-8 -*-
from flask import render_template

from . import receipt_printing_bp as receipt_printing


@receipt_printing.route('/index')
def index():
    return render_template('receipt_printing/index.html')


@receipt_printing.route('/landing')
def landing():
    return render_template('receipt_printing/landing.html')

