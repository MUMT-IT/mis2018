from dateutil import parser
from flask import render_template, request, jsonify
from flask_login import login_required

from . import studbp as stud
from app.eduqa.models import EduQACourseAssignmentSession, EduQACurriculumnRevision


@stud.route('/')
def index():
    return render_template('studs/index.html')


@stud.route('/workload/revisions/<int:revision_id>/assignments')
def show_assignments(revision_id):
    next_url = request.args.get('next_url')
    revision = EduQACurriculumnRevision.query.get(revision_id)
    student_year = request.args.get('student_year', 'ปี 1')
    return render_template('studs/assignments.html',
                           student_year=student_year, revision_id=revision_id, revision=revision, next_url=next_url)


@stud.route('/api/assignments')
@login_required
def get_assignments():
    student_year = request.args.get('student_year', 'ปี 1')
    revision_id = request.args.get('revision_id')
    events = []
    end = request.args.get('end')
    start = request.args.get('start')
    if start:
        start = parser.isoparse(start)
    if end:
        end = parser.isoparse(end)
    if revision_id:
        for evt in EduQACourseAssignmentSession.query \
                .filter(EduQACourseAssignmentSession.start >= start,
                        EduQACourseAssignmentSession.start <= end,
                        EduQACourseAssignmentSession.course.has(revision_id=int(revision_id)),
                        EduQACourseAssignmentSession.course.has(student_year=student_year)):
            events.append(evt.to_event())
    return jsonify(events)
