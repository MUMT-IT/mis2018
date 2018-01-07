import datetime
from flask import render_template
from ..models import Student
from . import studbp as stud


@stud.route('/')
def index():
    stud = Student.query.first()
    print(stud.th_first_name)
    return '<h2>Welcome to Students Index Page.</h2>'


@stud.route('/checkin/<int:class_id>/<stud_id>')
def checkin(class_id, stud_id):
    if not class_id or not stud_id:
        return render_template(student={})
    else:
        deadline = datetime.datetime.strptime('2018/01/07 10:00:00', '%Y/%m/%d %H:%M:%S')
        student = Student.query.get(stud_id)
        klass = {'title': 'Transformative'}
        checkin = datetime.datetime.now()
        delta = checkin - deadline
        elapsed_mins = delta.total_seconds() / 60.0
        if elapsed_mins < 0:
            status = 'is-success'
        elif elapsed_mins < 15.0:
            status = 'is-warning'
        else:
            status = 'is-danger'
        return render_template('/studs/checkin.html',
                student=student,
                klass=klass,
                checkin=checkin,
                status=status)