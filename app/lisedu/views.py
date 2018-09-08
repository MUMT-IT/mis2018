from . import lisedu as lis
from flask import render_template

@lis.route('/')
def main_page():
    return render_template('/lisedu/main.html')