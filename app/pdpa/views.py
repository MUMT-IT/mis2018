from flask import render_template

from . import pdpa_blueprint as pdpa


@pdpa.route('/')
def index():
    return render_template('pdpa/index.html')