from flask import render_template
from . import eduqa_bp as edu


@edu.route('/qa/')
def index():
    return render_template('eduqa/QA/index.html')


@edu.route('/qa/mtc/criteria1')
def criteria1_index():
    return render_template('eduqa/QA/mtc/criteria1.html')
