import datetime
import pytz
from flask import render_template
from ..models import Student, ClassCheckIn, StudentCheckInRecord, Class
from ..main import db
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
        tz = pytz.timezone('Asia/Bangkok')
        fmt = '%Y-%m-%d %H:%M:%S'
        class_checkin = ClassCheckIn.query.filter_by(class_id=class_id).first()
        today = datetime.datetime.now(tz=tz).date()
        deadline_str = '{0}-{1:02}-{2:02}'.format(today.year, today.month, today.day)
        deadline_str += ' ' + class_checkin.deadline
        deadline = tz.localize(datetime.datetime.strptime(deadline_str, fmt))
        student = Student.query.get(stud_id)
        klass = Class.query.get(class_id)
        checkin = datetime.datetime.now(tz=tz)
        delta = checkin - deadline
        elapsed_mins = delta.total_seconds() / 60.0
        if elapsed_mins < 0:
            status = 'is-success'
        elif elapsed_mins < 15.0:
            status = 'is-warning'
        else:
            status = 'is-danger'
        chk_record = StudentCheckInRecord(
                            stud_id=stud_id,
                            classchk_id=class_checkin.id,
                            check_in_time=checkin,
                            check_in_status=status,
                            elapsed_mins=elapsed_mins
                        )
        db.session.add(chk_record)
        db.session.commit()
        return render_template('/studs/checkin.html',
                student=student,
                klass=klass,
                checkin=checkin,
                deadline=deadline,
                status=status)