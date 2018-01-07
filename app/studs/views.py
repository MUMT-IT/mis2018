import datetime
from flask import render_template
from . import studbp as stud


@stud.route('/')
def index():
    return '<h2>Welcome to Students Index Page.</h2>'


@stud.route('/checkin/<int:class_id>/<stud_id>')
def checkin(class_id, stud_id):
    if not class_id or not stud_id:
        return render_template(student={})
    else:
        chk_in_time = datetime.datetime.now()
        klass = {'title': 'Transformative'}
        student = {'name': 'Suchunya Preeyanon', 'checkin': chk_in_time}
        return render_template('/studs/checkin.html', student=student, klass=klass)