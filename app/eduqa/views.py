from flask import render_template
from . import eduqa_bp as edu
from forms import ProgramForm


@edu.route('/qa/')
def index():
    return render_template('eduqa/QA/index.html')


@edu.route('/qa/mtc/criteria1')
def criteria1_index():
    return render_template('eduqa/QA/mtc/criteria1.html')


@edu.route('/qa/program/edit')
def edit_program():
    form = ProgramForm()
    return render_template('eduqa/QA/program_edit.html', form=form)