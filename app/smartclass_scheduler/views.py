from flask import request, url_for, render_template, redirect
from . import smartclass_scheduler_blueprint as smartclass


@smartclass.route('/')
def index():
    return render_template('smartclass_scheduler/index.html')