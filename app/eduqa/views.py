# -*- coding:utf-8 -*-
import io
import time
from collections import defaultdict

import pandas as pd
import json

import arrow
from psycopg2.extras import DateTimeRange
from flask import render_template, request, flash, redirect, url_for, session, jsonify, make_response, send_file
from flask_login import current_user, login_required
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Image, TableStyle, Table, KeepTogether, Spacer
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy.orm import make_transient
from sqlalchemy import extract, or_

from . import eduqa_bp as edu
from app.eduqa.forms import *
from app.room_scheduler.models import EventCategory
from app.staff.models import StaffPersonalInfo
from app.roles import education_permission

from pytz import timezone

localtz = timezone('Asia/Bangkok')


def is_datetime_valid(start, end):
    if start > end:
        flash(u'วันเริ่มกิจกรรมมาหลังวันสิ้นสุดกิจกรรมโปรดแก้ไขข้อมูล', 'warning')
        return False
    elif start == end:
        flash(u'เวลาในกิจกรรมการสอนเป็นศูนย์ชั่วโมง กรุณาตรวจสอบข้อมูล', 'warning')
        return False
    else:
        return True


@edu.route('/qa/')
def index():
    return render_template('eduqa/QA/index.html')


@edu.route('/qa/mtc/criteria1')
@login_required
def criteria1_index():
    return render_template('eduqa/QA/mtc/criteria1.html')


@edu.route('/qa/academic-staff/')
@login_required
def academic_staff_info_main():
    return render_template('eduqa/QA/staff/index.html')


@edu.route('/qa/academic-staff/academic-position/edit', methods=['GET', 'POST'])
@login_required
def academic_position_edit():
    form = AcademicPositionRecordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            record = StaffAcademicPositionRecord()
            form.populate_obj(record)
            record.personal_info = current_user.personal_info
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.academic_staff_info_main'))
        else:
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/staff/academic_position_edit.html', form=form)


@edu.route('/qa/academic-staff/academic-position/remove/<int:record_id>')
@login_required
def academic_position_remove(record_id):
    record = StaffAcademicPositionRecord.query.get(record_id)
    if record:
        db.session.delete(record)
        db.session.commit()
        flash(u'ลบรายการเรียบร้อย', 'success')
    else:
        flash(u'ไม่พบรายการในระบบ', 'warning')
    return redirect(url_for('eduqa.academic_staff_info_main'))


@edu.route('/qa/academic-staff/education-record/add', methods=['GET', 'POST'])
@login_required
def add_education_record():
    form = EduDegreeRecordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            record = StaffEduDegree()
            form.populate_obj(record)
            record.personal_info = current_user.personal_info
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.academic_staff_info_main'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/staff/education_edit.html', form=form)


@edu.route('/qa/academic-staff/education-record/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_education_record(record_id):
    record = StaffEduDegree.query.get(record_id)
    form = EduDegreeRecordForm(obj=record)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(record)
            record.personal_info = current_user.personal_info
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.academic_staff_info_main'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/staff/education_edit.html', form=form)


@edu.route('/qa/academic-staff/education-record/remove/<int:record_id>', methods=['GET', 'POST'])
@login_required
def remove_education_record(record_id):
    record = StaffEduDegree.query.get(record_id)
    if record:
        db.session.delete(record)
        db.session.commit()
        flash(u'ลบรายการเรียบร้อย', 'success')
    else:
        flash(u'ไม่พบรายการในระบบ', 'warning')
    return redirect(url_for('eduqa.academic_staff_info_main'))


@edu.route('/qa/program')
@login_required
def show_programs():
    programs = EduQAProgram.query.all()
    return render_template('eduqa/QA/program.html', programs=programs)


@edu.route('/qa/programs/add', methods=['POST', 'GET'])
@login_required
def add_program():
    form = EduProgramForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            program = EduQAProgram()
            form.populate_obj(program)
            db.session.add(program)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.index'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/program_edit.html', form=form)


@edu.route('/qa/programs/edit/<int:program_id>', methods=['POST', 'GET'])
@login_required
def edit_program(program_id):
    program = EduQAProgram.query.get(program_id)
    form = EduProgramForm(obj=program)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(program)
            db.session.add(program)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.index'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/program_edit.html', form=form)


@edu.route('/qa/curriculums')
@login_required
def show_curriculums():
    programs = EduQAProgram.query.all()
    return render_template('eduqa/QA/curriculums.html', programs=programs)


@edu.route('/qa/curriculums/add', methods=['POST', 'GET'])
@login_required
def add_curriculum():
    form = EduCurriculumnForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            curriculum = EduQACurriculum()
            form.populate_obj(curriculum)
            db.session.add(curriculum)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.show_curriculums'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/curriculumn_edit.html', form=form)


@edu.route('/qa/curriculums/list')
@login_required
def list_curriculums():
    programs = EduQAProgram.query.all()
    return render_template('eduqa/QA/curriculum_list.html', programs=programs)


@edu.route('/backoffice/qa/curriculums/list')
def backoffice_list_curriculums():
    programs = EduQAProgram.query.all()
    return render_template('eduqa/QA/backoffice/curriculum_list.html', programs=programs)


@edu.route('/qa/curriculums/<int:curriculum_id>/revisions')
@login_required
def show_revisions(curriculum_id):
    curriculum = EduQACurriculum.query.get(curriculum_id)
    return render_template('eduqa/QA/curriculum_revisions.html', curriculum=curriculum)


@edu.route('/qa/curriculums/<int:curriculum_id>/revisions/add', methods=['GET', 'POST'])
@login_required
def add_revision(curriculum_id):
    form = EduCurriculumnRevisionForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            revision = EduQACurriculumnRevision()
            form.populate_obj(revision)
            db.session.add(revision)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.show_revisions', curriculum_id=curriculum_id))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/curriculum_revision_edit.html', form=form)


@edu.route('/qa/revisions/<int:revision_id>')
@login_required
def show_revision_detail(revision_id):
    display_my_courses_only = request.args.get('display_my_courses_only')
    if not display_my_courses_only:
        display_my_courses_only = session.get('display_my_courses_only', 'false')
    else:
        session['display_my_courses_only'] = display_my_courses_only
    revision = EduQACurriculumnRevision.query.get(revision_id)
    instructor = EduQAInstructor.query.filter_by(account=current_user).first()
    if instructor and display_my_courses_only == 'true':
        display_my_courses_only = True
        courses = [c.course for c in EduQACourseInstructorAssociation.query.filter_by(instructor=instructor)
                   if c.course in revision.courses]
    elif not instructor or display_my_courses_only == 'false':
        display_my_courses_only = False
        courses = revision.courses

    my_courses = [c.course for c in EduQACourseInstructorAssociation.query.filter_by(instructor=instructor)
                  if c.course in revision.courses]
    return render_template('eduqa/QA/curriculum_revision_detail.html',
                           revision=revision,
                           display_my_course_only=display_my_courses_only,
                           instructor=instructor,
                           my_courses=my_courses,
                           courses=courses)


@edu.route('/qa/revisions/<int:revision_id>/courses/add', methods=['GET', 'POST'])
@login_required
def add_course(revision_id):
    form = EduCourseForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            course = EduQACourse()
            form.populate_obj(course)
            course.en_code = course.en_code.replace(' ', '')
            course.th_code = course.th_code.replace(' ', '')
            course.revision_id = revision_id
            course.creator = current_user
            course.created_at = arrow.now('Asia/Bangkok').datetime
            course.updater = current_user
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(course)
            db.session.commit()
            flash(u'บันทึกข้อมูลรายวิชาเรียบร้อย', 'success')
            return redirect(url_for('eduqa.show_revision_detail', revision_id=revision_id))
        else:
            flash(u'เกิดความผิดพลาดบางประการ กรุณาตรวจสอบข้อมูล', 'warning')
    return render_template('eduqa/QA/course_edit.html', form=form, revision_id=revision_id)


@edu.route('/qa/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    course = EduQACourse.query.get(course_id)
    form = EduCourseForm(obj=course)
    refresh = request.args.get('refresh', 'false')
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(course)
            course.updater = current_user
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(course)
            db.session.commit()
            resp = make_response()
            resp.headers['HX-Swap'] = 'none'
            resp.headers['HX-Trigger'] = json.dumps(
                {'loadData': '', 'closeModal': '', 'successAlert': 'บันทึกข้อมูลแล้ว'})
            resp.headers['HX-Refresh'] = refresh
            return resp
        else:
            resp = make_response()
            resp.headers['HX-Swap'] = 'none'
            resp.headers['HX-Trigger'] = json.dumps({'closeModal': '', 'dangerAlert': 'เกิดข้อผิดพลาด'})
            resp.headers['HX-Refresh'] = refresh
            if refresh == 'true':
                flash('เกิดข้อผิดพลาด กรุณาตรวจสอบข้อมูล', 'danger')
            return resp
    return render_template('eduqa/partials/course_info_form.html',
                           form=form, course_id=course_id, refresh=refresh)


@edu.route('/qa/courses/<int:course_id>/delete')
@login_required
def delete_course(course_id):
    course = EduQACourse.query.get(course_id)
    revision_id = course.revision_id
    if course:
        db.session.delete(course)
        db.session.commit()
        flash(u'ลบรายวิชาเรียบร้อยแล้ว', 'success')
    else:
        flash(u'ไม่พบรายการนี้', 'warning')
    return redirect(url_for('eduqa.show_revision_detail', revision_id=revision_id))


@edu.route('/qa/courses/<int:course_id>/copy', methods=['GET', 'POST'])
@login_required
def copy_course(course_id):
    course = EduQACourse.query.get(course_id)
    db.session.expunge(course)
    make_transient(course)
    course.th_name = course.th_name + '(copy)'
    course.th_code = course.th_code + '(copy)'
    course.academic_year = None
    course.creator = current_user
    course.created_at = arrow.now('Asia/Bangkok').datetime
    course.updater = current_user
    course.updated_at = arrow.now('Asia/Bangkok').datetime
    course.id = None
    the_course = EduQACourse.query.get(course_id)
    for instructor in the_course.instructors:
        course.instructors.append(instructor)
    for ss in the_course.sessions:
        s = EduQACourseSession(
            start=ss.start,
            end=ss.end,
            course=course,
            type_=ss.type_,
            desc=ss.desc,
        )
        for instructor in ss.instructors:
            s.instructors.append(instructor)
        course.sessions.append(s)
    try:
        db.session.add(course)
        db.session.commit()
    except:
        flash(u'ไม่สามารถคัดลอกรายวิชาได้', 'warning')
    else:
        flash(u'รายวิชาได้รับการคัดลอกเรียบร้อยแล้ว', 'success')
    return redirect(url_for('eduqa.show_course_detail', course_id=course.id))


@edu.route('/qa/courses/<int:course_id>', methods=['GET', 'POST'])
@login_required
def show_course_detail(course_id):
    course = EduQACourse.query.get(course_id)
    grading_form = EduGradingSchemeForm()
    grading_form.grading_scheme.data = course.grading_scheme
    admin = None
    instructor = None
    instructor_role = None
    for asc in course.course_instructor_associations:
        if asc.role and asc.role.admin:
            admin = asc.instructor
        if asc.instructor.account == current_user:
            instructor = asc.instructor
            instructor_role = asc.role
    return render_template('eduqa/QA/course_detail.html', course=course,
                           instructor=instructor,
                           grading_form=grading_form,
                           admin=admin,
                           instructor_role=instructor_role)


@edu.route('/qa/courses/<int:course_id>/public')
def show_course_detail_public(course_id):
    course = EduQACourse.query.get(course_id)
    source = request.args.get('source')
    grading_form = EduGradingSchemeForm()
    grading_form.grading_scheme.data = course.grading_scheme
    admin = None
    instructor = None
    instructor_role = None
    for asc in course.course_instructor_associations:
        if asc.role and asc.role.admin:
            admin = asc.instructor
        if asc.instructor.account == current_user:
            instructor = asc.instructor
            instructor_role = asc.role
    return render_template('eduqa/QA/course_detail_public.html', course=course,
                           instructor=instructor,
                           grading_form=grading_form,
                           admin=admin,
                           source=source,
                           instructor_role=instructor_role)


@edu.route('/qa/courses/<int:course_id>/report', methods=['GET', 'POST'])
@login_required
def report_course_detail(course_id):
    course = EduQACourse.query.get(course_id)
    grading_form = EduGradingSchemeForm()
    grading_form.grading_scheme.data = course.grading_scheme
    admin = None
    instructor = None
    instructor_role = None
    for asc in course.course_instructor_associations:
        if asc.role and asc.role.admin:
            admin = asc.instructor
        if asc.instructor.account == current_user:
            instructor = asc.instructor
            instructor_role = asc.role
    return render_template('eduqa/QA/course_report.html', course=course,
                           instructor=instructor,
                           grading_form=grading_form,
                           admin=admin,
                           instructor_role=instructor_role)


@edu.route('/qa/courses/<int:course_id>/report/public', methods=['GET', 'POST'])
def report_course_detail_public(course_id):
    course = EduQACourse.query.get(course_id)
    grading_form = EduGradingSchemeForm()
    grading_form.grading_scheme.data = course.grading_scheme
    admin = None
    instructor = None
    instructor_role = None
    for asc in course.course_instructor_associations:
        if asc.role and asc.role.admin:
            admin = asc.instructor
        if asc.instructor.account == current_user:
            instructor = asc.instructor
            instructor_role = asc.role
    return render_template('eduqa/QA/backoffice/course_report_public.html', course=course,
                           instructor=instructor,
                           grading_form=grading_form,
                           admin=admin,
                           instructor_role=instructor_role)


@edu.route('/qa/courses/<int:course_id>/instructors/add', methods=['GET', 'POST'])
@login_required
def add_instructor(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'POST':
        for pid in request.form.getlist('employees'):
            p = StaffPersonalInfo.query.get(pid)
            instructor = EduQAInstructor.query.filter_by(account_id=p.staff_account.id).first()
            if not instructor:
                instructor = EduQAInstructor(account_id=p.staff_account.id)
            course.course_instructor_associations.append(
                EduQACourseInstructorAssociation(instructor=instructor)
            )
            course.updater = current_user
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(instructor)
        db.session.add(course)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('eduqa/partials/instructor_add_form.html', course_id=course_id)


@edu.route('/qa/courses/<int:course_id>/instructors/roles/assignment', methods=['GET', 'POST'])
@login_required
def assign_roles(course_id):
    course = EduQACourse.query.get(course_id)
    form = EduCourseInstructorRoleForm()
    if form.validate_on_submit():
        for form_field in form.roles:
            course_inst = EduQACourseInstructorAssociation.query \
                .filter_by(course_id=course_id).filter_by(instructor_id=int(form_field.instructor_id.data)).first()
            course_inst.role = form_field.role.data
            db.session.add(course_inst)
        db.session.commit()
        return redirect(url_for('eduqa.show_course_detail', course_id=course_id))

    for asc in course.course_instructor_associations:
        form.roles.append_entry(asc)
        if asc.instructor.account == current_user:
            instructor = asc.instructor
            instructor_role = asc.role
        else:
            instructor = None
            instructor_role = None
    return render_template('eduqa/QA/role_edit.html', course=course, instructor=instructor, form=form)


@edu.route('/qa/courses/<int:course_id>/instructors/remove/<int:instructor_id>')
@login_required
def remove_instructor_from_list(course_id, instructor_id):
    course = EduQACourse.query.get(course_id)
    instructor = EduQAInstructor.query.get(instructor_id)
    for s in course.sessions:
        if instructor in s.instructors:
            s.instructors.remove(instructor)
            db.session.add(s)
    course.instructors.remove(instructor)
    course.updater = current_user
    course.updated_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(course)
    db.session.commit()
    flash(u'ลบรายชื่อผู้สอนเรียบร้อยแล้ว', 'success')
    return redirect(url_for('eduqa.show_course_detail', course_id=course_id))


@edu.route('/qa/courses/<int:course_id>/sessions/add', methods=['GET', 'POST'])
@login_required
def add_session(course_id):
    course = EduQACourse.query.get(course_id)
    InstructorForm = create_instructors_form(course)
    event_category = EventCategory.query.filter_by(category='การเรียนการสอน').first()
    form = InstructorForm()
    if request.method == 'POST':
        for event_form in form.events:
            event_form.start.data = arrow.get(form.start.data, 'Asia/Bangkok').datetime
            event_form.end.data = arrow.get(form.end.data, 'Asia/Bangkok').datetime
            event_form.category.data = event_category
            event_form.title.data = f'{course.en_code}'
            event_form.datetime.data = DateTimeRange(lower=event_form.start.data,
                                                     upper=event_form.end.data,
                                                     bounds='[]')
        if form.validate_on_submit():
            new_session = EduQACourseSession()
            form.populate_obj(new_session)
            new_session.course = course
            new_session.start = arrow.get(form.start.data, 'Asia/Bangkok').datetime
            new_session.end = arrow.get(form.end.data, 'Asia/Bangkok').datetime
            if not is_datetime_valid(new_session.start, new_session.end):
                form.start.data = new_session.start
                form.end.data = new_session.end
                return render_template('eduqa/QA/session_edit.html',
                                       form=form, course=course, localtz=localtz)
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            course.updater = current_user
            db.session.add(new_session)
            db.session.commit()
            flash(u'เพิ่มรายการสอนเรียบร้อยแล้ว', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            flash(u'เกิดปัญหาในการบันทึกข้อมูล', 'warning')
    return render_template('eduqa/QA/session_edit.html', form=form, course=course, localtz=localtz)


@edu.route('/qa/courses/<int:course_id>/sessions/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_session(course_id, session_id):
    course = EduQACourse.query.get(course_id)
    event_category = EventCategory.query.filter_by(category='การเรียนการสอน').first()
    a_session = EduQACourseSession.query.get(session_id)
    InstructorForm = create_instructors_form(course)
    form = InstructorForm(obj=a_session)
    if request.method == 'POST':
        for event_form in form.events:
            if event_form.room.data:
                event_form.category.data = event_category
                event_form.start.data = arrow.get(form.start.data, 'Asia/Bangkok').datetime
                event_form.end.data = arrow.get(form.end.data, 'Asia/Bangkok').datetime
                event_form.title.data = f'{course.en_code}'
                event_form.datetime.data = DateTimeRange(lower=event_form.start.data,
                                                         upper=event_form.end.data,
                                                         bounds='[]')
        if form.validate_on_submit():
            form.populate_obj(a_session)
            a_session.course = course
            course.updater = current_user
            a_session.start = arrow.get(form.start.data, 'Asia/Bangkok').datetime
            a_session.end = arrow.get(form.end.data, 'Asia/Bangkok').datetime
            if not is_datetime_valid(a_session.start, a_session.end):
                form.start.data = a_session.start
                form.end.data = a_session.end
                return render_template('eduqa/QA/session_edit.html',
                                       form=form, course=course, localtz=localtz)
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(a_session)
            db.session.commit()
            flash(u'แก้ไขรายการสอนเรียบร้อยแล้ว', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            for field, error in form.errors.items():
                flash('{}: {}'.format(field, error), 'danger')
    return render_template('eduqa/QA/session_edit.html', form=form, course=course, session_id=session_id,
                           localtz=localtz)


@edu.route('/qa/courses/<int:course_id>/sessions/<int:session_id>/report', methods=['GET', 'POST'])
@login_required
def report_session(course_id, session_id):
    session = EduQACourseSession.query.get(session_id)
    form = EduCourseSessionReportForm(obj=session)
    if not form.duration.data:
        form.duration.data = session.total_minutes
    if form.validate_on_submit():
        form.populate_obj(session)
        db.session.add(session)
        db.session.commit()
        return redirect(url_for('eduqa.report_course_detail', course_id=course_id, _anchor='section-4'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('eduqa/QA/session_report.html', form=form, session=session)


@edu.route('/qa/courses/<int:course_id>/sessions/<int:session_id>/duplicate', methods=['GET', 'POST'])
@login_required
def duplicate_session(course_id, session_id):
    course = EduQACourse.query.get(course_id)
    a_session = EduQACourseSession.query.get(session_id)
    new_session = EduQACourseSession(
        course_id=course_id,
        start=a_session.start,
        end=a_session.end,
        type_=a_session.type_,
        desc=a_session.desc,
        instructors=a_session.instructors,
        format=a_session.format,
    )
    for topic in a_session.topics:
        new_topic = EduQACourseSessionTopic(
            topic=topic.topic,
            method=topic.method,
        )
        new_session.topics.append(new_topic)
        db.session.add(new_topic)

    db.session.add(new_session)
    db.session.commit()
    flash(u'เพิ่มรายการสอนเรียบร้อยแล้ว', 'success')
    return redirect(url_for('eduqa.show_course_detail', course_id=course.id))


@edu.route('/qa/sessions/<int:session_id>')
@login_required
def delete_session(session_id):
    a_session = EduQACourseSession.query.get(session_id)
    course_id = a_session.course.id
    if a_session:
        db.session.delete(a_session)
        db.session.commit()
        flash(u'ลบรายการเรียบร้อยแล้ว', 'success')
    else:
        flash(u'ไม่พบรายการ', 'warning')
    return redirect(url_for('eduqa.show_course_detail', course_id=course_id))


@edu.route('/qa/courses/<int:course_id>/sessions/<int:session_id>/detail/add', methods=['GET', 'POST'])
@login_required
def add_session_detail(course_id, session_id):
    course = EduQACourse.query.get(course_id)
    a_session = EduQACourseSession.query.get(session_id)
    session_detail = EduQACourseSessionDetail.query \
        .filter_by(session_id=session_id, staff_id=current_user.id).first()
    EduCourseSessionDetailForm = CourseSessionDetailFormFactory(a_session.type_)
    factor = 1
    if session_detail:
        form = EduCourseSessionDetailForm(obj=session_detail)
        factor = session_detail.factor if session_detail.factor else 1
    else:
        form = EduCourseSessionDetailForm()

    if form.validate_on_submit():
        if session_detail:
            form.populate_obj(session_detail)
            db.session.add(session_detail)
            db.session.commit()
            flash(u'แก้ไขรายละเอียดการสอนเรียบร้อยแล้ว', 'success')
        else:
            new_detail = EduQACourseSessionDetail()
            form.populate_obj(new_detail)
            new_detail.session_id = session_id
            new_detail.staff_id = current_user.id
            db.session.add(new_detail)
            db.session.commit()
            flash(u'เพิ่มรายละเอียดการสอนเรียบร้อยแล้ว', 'success')
        return redirect(url_for('eduqa.show_course_detail', course_id=course_id))
    return render_template('eduqa/QA/staff/session_detail_edit.html',
                           form=form, course=course, a_session=a_session, factor=factor)


@edu.route('/qa/courses/<int:course_id>/sessions/<int:session_id>/instructor/<int:instructor_id>/detail')
@login_required
def view_session_detail(session_id, course_id, instructor_id):
    instructor = EduQAInstructor.query.get(instructor_id)
    a_session = EduQACourseSession.query.get(session_id)
    course = EduQACourse.query.get(course_id)
    session_detail = EduQACourseSessionDetail.query.filter_by(staff_id=current_user.id, session_id=session_id).first()
    return render_template('eduqa/QA/staff/session_detail_view.html',
                           instructor=instructor,
                           course=course,
                           session_detail=session_detail, a_session=a_session)


@edu.route('/api/qa/courses/<int:course_id>/sessions/topics', methods=['POST'])
@login_required
def add_session_topic(course_id):
    course = EduQACourse.query.get(course_id)
    EduCourseSessionForm = create_instructors_form(course)
    form = EduCourseSessionForm()
    form.topics.append_entry()
    topic_form = form.topics[-1]
    template = u"""
        <div class="field">
            <label class="label">{} {}</label>
            <div class="control">
                {}
            </div>
        </div>
    """
    return template.format(topic_form.topic.label,
                           len(form.topics),
                           topic_form.topic(class_="input"))


@edu.route('/api/qa/courses/<int:course_id>/sessions/topics', methods=['DELETE'])
@login_required
def delete_session_topic(course_id):
    course = EduQACourse.query.get(course_id)
    EduCourseSessionForm = create_instructors_form(course)
    form = EduCourseSessionForm()
    if len(form.topics) > 1:
        form.topics.pop_entry()
    template = ''
    for n, topic in enumerate(form.topics, start=1):
        template += u"""
            <div class="field">
                <label class="label">{} {}</label>
                <div class="control">
                    {}
                </div>
            </div>
        """.format(topic.topic.label, n, topic.topic(class_="input"))
    return template


@edu.route('/api/qa/courses/<int:course_id>/sessions/rooms', methods=['POST'])
@login_required
def add_session_room_event(course_id):
    course = EduQACourse.query.get(course_id)
    EduCourseSessionForm = create_instructors_form(course)
    form = EduCourseSessionForm()
    form.events.append_entry()
    event_form = form.events[-1]
    template = u"""
    <div id="{}">
        <div class="field">
            <label class="label">{}</label>
            {}
            <span id="availability-{}"></span>
        </div>
        <div class="field">
            <label class="label">{}</label>
            <div class="control">
            {}
            </div>
        </div>
    <div>
    """
    resp = template.format(event_form.name,
                           event_form.room.label,
                           event_form.room(class_="js-example-basic-single"),
                           event_form.room.name,
                           event_form.request.label,
                           event_form.request(class_="input"),
                           )
    resp = make_response(resp)
    resp.headers['HX-Trigger-After-Swap'] = 'activateSelect2js'
    return resp


@edu.route('/api/qa/courses/<int:course_id>/sessions/rooms', methods=['DELETE'])
@login_required
def remove_session_room_event(course_id):
    course = EduQACourse.query.get(course_id)
    EduCourseSessionForm = create_instructors_form(course)
    form = EduCourseSessionForm()
    form.events.pop_entry()
    resp = ''
    for event_form in form.events:
        template = u"""
        <div id="{}" hx-preserve>
            <div class="field">
                <label class="label">{}</label>
                {}
                <span id="availability-{}"></span>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                {}
                </div>
            </div>
        </div>
        """.format(event_form.name,
                   event_form.room.label,
                   event_form.room(class_="js-example-basic-single"),
                   event_form.room.name,
                   event_form.request.label,
                   event_form.request(class_="input")
                   )
        resp += template
    if len(form.events.entries) == 0:
        resp = '<p>ไม่มีการใช้ห้องสำหรับกิจกรรม</p>'
    resp = make_response(resp)
    return resp


@edu.route('/api/qa/courses/<int:course_id>/sessions/<int:session_id>/roles', methods=['POST'])
@login_required
def add_session_role(course_id, session_id):
    session = EduQACourseSession.query.get(session_id)
    EduCourseSessionDetailForm = CourseSessionDetailFormFactory(session.type_)
    form = EduCourseSessionDetailForm()
    form.roles.append_entry()
    role_form = form.roles[-1]
    template = u"""
        <div class="field">
            <label class="label">{}</label>
            <div class="select">
                {}
            </div>
        </div>
        <div class="field">
            <label class="label">{}</label>
            <div class="control">
                {}
            </div>
        </div>
    """
    return template.format(role_form.role_item.label,
                           role_form.role_item(),
                           role_form.detail.label,
                           role_form.detail(class_="input"))


@edu.route('/api/qa/courses/<int:course_id>/sessions/<int:session_id>/roles', methods=['DELETE'])
@login_required
def delete_session_role(course_id, session_id):
    session = EduQACourseSession.query.get(session_id)
    EduCourseSessionDetailForm = CourseSessionDetailFormFactory(session.type_)
    form = EduCourseSessionDetailForm()
    if len(form.roles) > 1:
        form.roles.pop_entry()

    template = ''
    for n, role_form in enumerate(form.roles, start=1):
        template += u"""
            <div class="field">
                <label class="label">{}</label>
                <div class="select">
                    {}
                </div>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
        """.format(role_form.role_item.label,
                   role_form.role_item(),
                   role_form.detail.label,
                   role_form.detail(class_="textarea"))
    return template


@edu.route('/qa/courses/<int:course_id>/assignments/add', methods=['GET', 'POST'])
@login_required
def add_session_assignment(course_id):
    course = EduQACourse.query.get(course_id)
    AssignmentInstructorForm = create_assignment_instructors_form(course)
    form = AssignmentInstructorForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_session = EduQACourseAssignmentSession()
            form.populate_obj(new_session)
            new_session.course = course
            new_session.start = arrow.get(new_session.start, 'Asia/Bangkok').datetime
            new_session.end = arrow.get(new_session.end, 'Asia/Bangkok').datetime
            if not is_datetime_valid(new_session.start, new_session.end):
                form.start.data = new_session.start
                form.end.data = new_session.end
                return render_template('eduqa/QA/assignment_session_edit.html',
                                       form=form, course=course, localtz=localtz)
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            course.updater = current_user
            db.session.add(new_session)
            db.session.commit()
            flash(u'เพิ่มกิจกรรมเรียบร้อยแล้ว', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            flash(u'เกิดปัญหาในการบันทึกข้อมูล', 'warning')
    return render_template('eduqa/QA/assignment_session_edit.html', form=form, course=course, localtz=localtz)


@edu.route('/qa/courses/<int:course_id>/assignments/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_session_assignment(course_id, session_id):
    course = EduQACourse.query.get(course_id)
    a_session = EduQACourseAssignmentSession.query.get(session_id)
    AssignmentInstructorForm = create_assignment_instructors_form(course)
    form = AssignmentInstructorForm(obj=a_session)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(a_session)
            a_session.course = course
            course.updater = current_user
            a_session.start = arrow.get(a_session.start, 'Asia/Bangkok').datetime
            a_session.end = arrow.get(a_session.end, 'Asia/Bangkok').datetime
            if not is_datetime_valid(a_session.start, a_session.end):
                form.start.data = a_session.start
                form.end.data = a_session.end
                return render_template('eduqa/QA/session_edit.html',
                                       form=form, course=course, localtz=localtz)
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(a_session)
            db.session.commit()
            flash(u'แก้ไขรายการสอนเรียบร้อยแล้ว', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            for field, error in form.errors.items():
                flash('{}: {}'.format(field, error), 'danger')
    return render_template('eduqa/QA/assignment_session_edit.html',
                           form=form, course=course, session_id=session_id, localtz=localtz)


@edu.route('/qa/assignments/<int:session_id>')
@login_required
def delete_session_assignment(session_id):
    a_session = EduQACourseAssignmentSession.query.get(session_id)
    course_id = a_session.course.id
    if a_session:
        db.session.delete(a_session)
        db.session.commit()
        flash(u'ลบรายการเรียบร้อยแล้ว', 'success')
    else:
        flash(u'ไม่พบรายการ', 'warning')
    return redirect(url_for('eduqa.show_course_detail', course_id=course_id))


@edu.route('/qa/courses/<int:course_id>/learning-outcomes-form-modal', methods=['GET', 'POST'])
@edu.route('/qa/courses/<int:course_id>/learning-outcomes-form-modal/<int:clo_id>',
           methods=['GET', 'POST', 'DELETE', 'PATCH'])
@login_required
def edit_clo(course_id, clo_id=None):
    course = EduQACourse.query.get(course_id)
    if clo_id:
        clo = EduQACourseLearningOutcome.query.get(clo_id)
        form = EduCourseLearningOutcomeForm(obj=clo)
        max_weight = (100 - course.total_clo_percent) + clo.score_weight
        min_weight = clo.total_score_weight
    else:
        form = EduCourseLearningOutcomeForm()
        max_weight = 100 - course.total_clo_percent
        min_weight = 0
        form.score_weight.data = max_weight
    if request.method == 'GET':
        return render_template('eduqa/partials/clo_form_modal.html',
                               max_weight=max_weight,
                               min_weight=min_weight,
                               form=form, course_id=course_id, clo_id=clo_id)
    elif request.method == 'POST':
        form = EduCourseLearningOutcomeForm()
        if form.validate_on_submit():
            new_clo = EduQACourseLearningOutcome()
            form.populate_obj(new_clo)
            new_clo.course_id = course_id
            db.session.add(new_clo)
            db.session.commit()
        else:
            resp = make_response()
            resp.headers['HX-Reswap'] = 'none'
            resp.headers['HX-Trigger-After-Swap'] = json.dumps({'closeModal': float(clo.course.total_clo_percent),
                                                                'dangerAlert': 'Required inputs not given.'})
            return resp
    elif request.method == 'PATCH':
        form.populate_obj(clo)
        db.session.add(clo)
        db.session.commit()
    elif request.method == 'DELETE':
        db.session.delete(clo)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Trigger-After-Swap'] = json.dumps({'closeModal': float(course.total_clo_percent)})
        return resp
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@edu.route('/qa/clos/<int:clo_id>/learning-activities', methods=['GET', 'POST'])
@edu.route('/qa/clos/<int:clo_id>/learning-activities/<int:pair_id>', methods=['GET', 'PATCH', 'POST', 'DELETE'])
@login_required
def edit_learning_activity(clo_id, pair_id=None):
    clo = EduQACourseLearningOutcome.query.get(clo_id)
    if request.method == 'GET':
        if pair_id:
            pair = EduQALearningActivityAssessmentPair.query.get(pair_id)
            form = EduCourseLearningActivityForm()
            form.learning_activity.data = pair.learning_activity
            form.assessments.choices = [(c.id, str(c)) for c in pair.learning_activity.assessments]
            form.assessments.data = pair.learning_activity_assessment_id
            form.score_weight.data = pair.score_weight
            form.note.data = pair.note
            max_score_weight = (clo.score_weight - clo.total_score_weight) + pair.score_weight
        else:
            form = EduCourseLearningActivityForm()
            form.learning_activity.data = EduQALearningActivity.query.first()
            form.assessments.choices = [(c.id, str(c)) for c in form.learning_activity.data.assessments]
            max_score_weight = clo.score_weight - clo.total_score_weight
            form.score_weight.data = max_score_weight

        return render_template('eduqa/partials/learning_activity_form_modal.html',
                               max_score_weight=max_score_weight,
                               form=form,
                               clo_id=clo_id,
                               pair_id=pair_id)
    elif request.method == 'PATCH':
        form = EduCourseLearningActivityForm()
        if form.validate_on_submit():
            activity = form.learning_activity.data
            assessment_id = form.assessments.data
            pair = EduQALearningActivityAssessmentPair.query.get(pair_id)
            pair.learning_activity_assessment_id = assessment_id
            pair.score_weight = form.score_weight.data
            pair.learning_activity = activity
            pair.note = form.note.data
        else:
            resp = make_response()
            resp.headers['Reswap'] = 'none'
            resp.headers['HX-Trigger-After-Swap'] = json.dumps({'closeModal': float(clo.course.total_clo_percent),
                                                                'dangerAlert': 'Required inputs not given.'})
            return resp
    elif request.method == 'POST':
        form = EduCourseLearningActivityForm()
        pair = EduQALearningActivityAssessmentPair(clo=clo,
                                                   learning_activity=form.learning_activity.data,
                                                   learning_activity_assessment_id=form.assessments.data,
                                                   note=form.note.data,
                                                   score_weight=form.score_weight.data)
    db.session.add(pair)
    db.session.commit()
    template = f'''
        <tr id="pair-id-{pair.id}">
            <td>{pair.learning_activity}
                <p class="help is-info">
                    {pair.note or ''}
                </p>
            </td>
            <td>
                {pair.learning_activity_assessment}
            </td>
            <td>
                {pair.score_weight or 0.0}%
            </td>
            <td>
                <a hx-target="#learning-activity-form"
                   hx-swap="innerHTML"
                   hx-get="{url_for('eduqa.edit_learning_activity', clo_id=clo.id, course_id=clo.course_id, pair_id=pair.id)}">
                   <span class="icon">
                       <i class="fas fa-pencil-alt has-text-primary"></i>
                   </span>
                </a>
                <a hx-delete="{url_for('eduqa.delete_learning_activity_assessment_pair', pair_id=pair.id)}"
                   hx-swap="outerHTML swap:1s"
                   hx-confirm="Are you sure?"
                   hx-target="closest tr">
                   <span class="icon">
                       <i class="far fa-trash-alt has-text-danger"></i>
                   </span>
                </a>
            </td>
        </tr>
        '''
    resp = make_response(template)
    resp.headers['HX-Trigger-After-Swap'] = json.dumps({'closeModal': float(clo.course.total_clo_percent)})
    return resp


@edu.route('/qa/clos/<int:clo_id>/learning-activities/<int:pair_id>/report', methods=['GET', 'PATCH'])
@login_required
def report_learning_activity(clo_id, pair_id=None):
    clo = EduQACourseLearningOutcome.query.get(clo_id)
    pair = EduQALearningActivityAssessmentPair.query.get(pair_id)
    form = EduCourseLearningActivityAssessmentReportForm(obj=pair)
    if request.method == 'GET':
        return render_template('eduqa/partials/learning_activity_report_form_modal.html',
                               form=form,
                               clo_id=clo_id,
                               pair_id=pair_id)
    elif request.method == 'PATCH':
        if form.validate_on_submit():
            form.populate_obj(pair)
            db.session.add(pair)
            db.session.commit()
            template = f'<span class="has-text-info"><strong>การสอน:</strong> {pair.problem_detail or "ไม่มี"}<br><strong>การประเมิน:</strong> {pair.assessment_problem_detail or "ไม่มี"}</span>'
            resp = make_response(template)
            resp.headers['HX-Trigger-After-Swap'] = json.dumps({'closeModal': float(clo.course.total_clo_percent),
                                                                'successAlert': 'Report has been saved.'})
            return resp


@edu.route('/qa/clos/<int:clo_id>/assessment-methods', methods=['POST'])
@edu.route('/qa/clos/<int:clo_id>/activities/<int:activity_id>/assessment-methods', methods=['POST'])
@login_required
def get_assessment_methods(clo_id, activity_id=None):
    form = EduCourseLearningActivityForm()
    activity = form.learning_activity.data
    if activity:
        form.assessments.choices = [(c.id, str(c)) for c in activity.assessments]
        if activity_id:
            form.assessments.data = [c.learning_activity_assessment_id for c in
                                     EduQALearningActivityAssessmentPair.query.filter_by(clo_id=clo_id,
                                                                                         learning_activity=activity)]
        return form.assessments()
    else:
        return ''


@edu.route('/qa/courses/<int:course_id>/grading-schemes', methods=['POST'])
@login_required
def update_grading_scheme(course_id):
    course = EduQACourse.query.get(course_id)
    form = EduGradingSchemeForm()
    resp = make_response()
    template = '''<table class="table pt-1" id="grading_scheme_items">
    <thead>
    <th>สัญลักษณ์</th>
    <th>คำอธิบาย</th>
    <th>เกณฑ์</th>
    </thead>
    <tbody>
    '''
    if form.validate_on_submit():
        form.populate_obj(course)
        db.session.add(course)
        db.session.commit()
        resp.headers['HX-Trigger-After-Swap'] = json.dumps({"successAlert": "Grading scheme has been changed."})
        for item in course.grading_scheme.items:
            criteria_item = item.criteria.filter_by(course_id=course_id).first()
            criteria = criteria_item.criteria if criteria_item else ''
            template += f'''
            <tr>
            <td>{item.symbol}</td>
            <td>{item.detail or ''}</td>
            <td>{criteria}</td>
            <tr>
            '''
    else:
        resp.headers['HX-Trigger-After-Swap'] = json.dumps({"dangerAlert": "Error happened."})
    template += '</tbody></table>'
    template += f'''
            <button class="button is-small is-rounded is-primary"
                    hx-target="#grading-scheme-items"
                    hx-swap="innerHTML"
                    hx-get="{url_for('eduqa.update_grading_scheme_criteria', course_id=course.id)}">
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
                <span>แก้ไขเกณฑ์</span>
            </button>
        '''
    resp.response = template
    return resp


@edu.route('/qa/courses/<int:course_id>/grading-scheme-criteria', methods=['GET', 'POST'])
@login_required
def update_grading_scheme_criteria(course_id):
    course = EduQACourse.query.get(course_id)
    resp = make_response()
    template = f'''<form hx-post='{url_for("eduqa.update_grading_scheme_criteria", course_id=course_id)}'>
    <table class="table pt-1" id="grading_scheme_items">
    <thead>
    <th>สัญลักษณ์</th>
    <th>คำอธิบาย</th>
    <th>เกณฑ์</th>
    </thead>
    <tbody>
    '''
    if request.method == 'GET':
        for item in course.grading_scheme.items:
            c = EduQAGradingSchemeItemCriteria.query.filter_by(course_id=course_id, scheme_item=item).first()
            if not c:
                c = EduQAGradingSchemeItemCriteria(course_id=course_id, scheme_item=item)
                db.session.add(c)
                db.session.commit()
            template += f'''
            <tr>
            <td>{item.symbol}</td>
            <td>{item.detail or ''}</td>
            <td>
                <input type="text" class="input" value="{item.criteria.filter_by(course_id=course_id).first().criteria
                                                         or ''}" name="{item.id}"/>
            </td>
            </tr>
            '''
        template += '</tbody></table>'
        template += '<button type="submit" class="button is-small is-rounded is-success">บันทึก</button></form>'

    if request.method == 'POST':
        for item_id, value in request.form.items():
            criteria_item = EduQAGradingSchemeItemCriteria.query.filter_by(scheme_item_id=int(item_id),
                                                                           course_id=course_id).first()
            criteria_item.criteria = value
            db.session.add(criteria_item)
        db.session.commit()
        for item in course.grading_scheme.items:
            template += f'''
            <tr>
            <td>{item.symbol}</td>
            <td>{item.detail or ''}</td>
            <td>{item.criteria.filter_by(course_id=course_id).first().criteria or ''}</td>
            </tr>
            '''
        template += '</tbody></table>'
        template += f'''
            <button class="button is-small is-rounded is-primary"
                    hx-target="#grading-scheme-items"
                    hx-swap="innerHTML"
                    hx-get="{url_for('eduqa.update_grading_scheme_criteria', course_id=course.id)}">
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
                <span>แก้ไขเกณฑ์</span>
            </button>
        '''
        resp.headers['HX-Trigger-After-Swap'] = json.dumps({"successAlert": "Grading scheme criteria have been saved."})
        # resp.headers['HX-Trigger-After-Swap'] = json.dumps({"dangerAlert": "Error happened."})
    resp.response = template
    return resp


@edu.route('/qa/learning-activity-assessment-method-pair/<int:pair_id>', methods=['DELETE'])
@login_required
def delete_learning_activity_assessment_pair(pair_id):
    pair = EduQALearningActivityAssessmentPair.query.get(pair_id)
    db.session.delete(pair)
    db.session.commit()
    return ''


@edu.route('/qa/course/<int:course_id>/formative-assessments', methods=['GET', 'POST'])
@edu.route('/qa/course/<int:course_id>/formative-assessments/<int:assessment_id>',
           methods=['GET', 'PATCH', 'POST', 'DELETE'])
@login_required
def edit_formative_assessment(course_id, assessment_id=None):
    if request.method == 'GET':
        if assessment_id:
            assessment = EduQAFormativeAssessment.query.get(assessment_id)
            form = EduFormativeAssessmentForm(obj=assessment)

            return render_template('eduqa/partials/formative_assessment_form_modal.html',
                                   form=form, course_id=course_id, assessment_id=assessment_id)
        else:
            form = EduFormativeAssessmentForm()
            return render_template('eduqa/partials/formative_assessment_form_modal.html',
                                   form=form, course_id=course_id)
    if request.method == 'POST':
        form = EduFormativeAssessmentForm()
        if form.validate_on_submit():
            assessment = EduQAFormativeAssessment()
            form.populate_obj(assessment)
            assessment.course_id = course_id
            db.session.add(assessment)
    elif request.method == 'PATCH':
        form = EduFormativeAssessmentForm()
        assessment = EduQAFormativeAssessment.query.get(assessment_id)
        form.populate_obj(assessment)
        db.session.add(assessment)
    elif request.method == 'DELETE':
        assessment = EduQAFormativeAssessment.query.get(assessment_id)
        db.session.delete(assessment)

    db.session.commit()
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@edu.route('/qa/course/<int:course_id>/materials/<mtype>', methods=['GET', 'POST'])
@edu.route('/qa/course/<int:course_id>/materials/<int:item_id>/<mtype>',
           methods=['GET', 'PATCH', 'POST', 'DELETE'])
@login_required
def edit_course_material(course_id, mtype, item_id=None):
    material_types = {
        'required': EduQACourseRequiredMaterials,
        'suggested': EduQACourseSuggestedMaterials,
        'resource': EduQACourseResources
    }
    material_forms = {
        'required': EduQACourseRequiredMaterialsForm,
        'suggested': EduQACourseSuggestedMaterialsForm,
        'resource': EduQACourseResourcesForm
    }
    if request.method == 'GET':
        if item_id:
            item = material_types[mtype].query.get(item_id)
            form = material_forms[mtype](obj=item)
            return render_template('eduqa/partials/materials_form_modal.html',
                                   mtype=mtype, form=form, course_id=course_id, item_id=item_id)
        else:
            form = material_forms[mtype]()
            return render_template('eduqa/partials/materials_form_modal.html',
                                   form=form, course_id=course_id, mtype=mtype)
    if request.method == 'POST':
        form = material_forms[mtype]()
        if form.validate_on_submit():
            item = material_types[mtype]()
            form.populate_obj(item)
            item.course_id = course_id
            db.session.add(item)
    elif request.method == 'PATCH':
        form = material_forms[mtype]()
        item = material_types[mtype].query.get(item_id)
        form.populate_obj(item)
        db.session.add(item)
    elif request.method == 'DELETE':
        item = material_types[mtype].query.get(item_id)
        db.session.delete(item)

    db.session.commit()
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@edu.route('/qa/course/<int:course_id>/revision-plan', methods=['GET', 'PATCH'])
@login_required
def edit_course_revision_plan(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.revision_plan = request.form.get('revision_plan')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.revision_plan}
            <a hx-get="{url_for('eduqa.edit_course_revision_plan', course_id=course.id)}"
               hx-target="#revision-plan" hx-swap="innerHTML swap:1s"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#revision-plan' hx-swap='innerHTML swap:1s'>
        <textarea name='revision_plan' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_course_revision_plan', course_id=course_id), course.revision_plan)


@edu.route('/qa/course/<int:course_id>/update-plan', methods=['GET', 'PATCH'])
@login_required
def edit_course_update_plan(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.update_plan = request.form.get('update_plan')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.update_plan}
            <a hx-get="{url_for('eduqa.edit_course_update_plan', course_id=course.id)}"
               hx-target="#update-plan" hx-swap="innerHTML swap:1s"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#update-plan' hx-swap='innerHTML swap:1s'>
        <textarea name='update_plan' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_course_update_plan', course_id=course_id), course.update_plan)


@edu.route('/qa/course/<int:course_id>/student-numbers', methods=['GET', 'PATCH'])
@login_required
def edit_course_student_numbers(course_id):
    course = EduQACourse.query.get(course_id)
    form = EduCourseStudentNumberForm(obj=course)
    if request.method == 'PATCH':
        form.populate_obj(course)
        db.session.add(course)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('eduqa/partials/student_numbers.html', form=form, course_id=course_id)


@edu.route('/qa/course/<int:course_id>/grade-deviation', methods=['GET', 'PATCH'])
@login_required
def edit_course_grade_deviation(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.grade_deviation = request.form.get('grade_deviation')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.grade_deviation}
            <a hx-get="{url_for('eduqa.edit_course_grade_deviation', course_id=course.id)}"
               hx-target="#grade-deviation" hx-swap="innerHTML swap:1s"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#grade-deviation' hx-swap='innerHTML swap:1s'>
        <textarea name='grade_deviation' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_course_grade_deviation', course_id=course_id), course.grade_deviation)


@edu.route('/qa/course/<int:course_id>/suggestion', methods=['GET', 'PATCH'])
@login_required
def edit_course_suggestion(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.course_suggestion = request.form.get('course-suggestion')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.course_suggestion}
            <a hx-get="{url_for('eduqa.edit_course_suggestion', course_id=course.id)}"
               hx-target="#course-suggestion" hx-swap="innerHTML swap:1s"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#course-suggestion' hx-swap='innerHTML swap:1s'>
        <textarea name='course-suggestion' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_course_suggestion', course_id=course_id), course.course_suggestion)


@edu.route('/qa/course/<int:course_id>/evaluation-plan', methods=['GET', 'PATCH'])
@login_required
def edit_course_evaluation_plan(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.evaluation_plan = request.form.get('evaluation_plan')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.evaluation_plan}
            <a hx-get="{url_for('eduqa.edit_course_evaluation_plan', course_id=course.id)}"
               hx-target="#evaluation-plan" hx-swap="innerHTML"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#evaluation-plan' hx-swap='innerHTML'>
        <textarea name='evaluation_plan' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_course_evaluation_plan', course_id=course_id),
               course.evaluation_plan,
               url_for('eduqa.edit_course_evaluation_plan', course_id=course_id)
               )


@edu.route('/qa/course/<int:course_id>/student-eval-major-comment', methods=['GET', 'PATCH'])
@login_required
def edit_student_eval_major_comment(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.student_eval_major_comment = request.form.get('student_eval_major_comment')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.revision_plan}
            <a hx-get="{url_for('eduqa.edit_student_eval_major_comment', course_id=course.id)}"
               hx-target="#student_eval_major_comment" hx-swap="innerHTML swap:1s"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#student-eval-major-comment' hx-swap='innerHTML swap:1s' hx-indicator="closest .button">
        <textarea name='student_eval_major_comment' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
            <span>save</span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_student_eval_major_comment', course_id=course_id),
               course.student_eval_major_comment or '')


@edu.route('/qa/course/<int:course_id>/grade-correction', methods=['GET', 'PATCH'])
@login_required
def edit_course_grade_correction(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.grade_correction = request.form.get('grade_correction')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.grade_correction}
            <a hx-get="{url_for('eduqa.edit_course_grade_correction', course_id=course.id)}"
               hx-target="#grade-correction" hx-swap="innerHTML"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#grade-correction' hx-swap='innerHTML swap:1s'>
        <textarea name='grade_correction' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_course_grade_correction', course_id=course_id), course.grade_correction)


@edu.route('/qa/course/<int:course_id>/grade-petition', methods=['GET', 'PATCH'])
@login_required
def edit_course_grade_petition(course_id):
    course = EduQACourse.query.get(course_id)
    if request.method == 'PATCH':
        course.grade_petition = request.form.get('grade_petition')
        db.session.add(course)
        db.session.commit()
        return f'''
            {course.grade_petition}
            <a hx-get="{url_for('eduqa.edit_course_grade_petition', course_id=course.id)}"
               hx-target="#grade-petition" hx-swap="innerHTML"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil has-text-primary"></i>
                </span>
            </a>
        '''

    return '''
    <form hx-patch='{}' hx-target='#grade-petition' hx-swap='innerHTML swap:1s'>
        <textarea name='grade_petition' class='textarea'>{}</textarea>
        <button type=submit class='button is-success mt-2' >
            <span class='icon'>
                <i class="fa-solid fa-floppy-disk"></i>
            </span>
        </button>
    </form>
    '''.format(url_for('eduqa.edit_course_grade_petition', course_id=course_id), course.grade_petition)


@edu.route('/qa/clos/<int:clo_id>/plos', methods=['GET', 'PATCH'])
@login_required
def edit_clo_plo(clo_id):
    clo = EduQACourseLearningOutcome.query.get(clo_id)
    EduQACLOAndPLOForm = create_clo_plo_form(clo.course.revision_id)
    form = EduQACLOAndPLOForm(obj=clo)
    if request.method == 'PATCH':
        form.populate_obj(clo)
        db.session.add(clo)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('eduqa/partials/clo_plo_form_modal.html', form=form, clo_id=clo_id)


@edu.route('/qa/revisions/<int:revision_id>/summary/hours')
@login_required
def show_hours_summary_all(revision_id):
    revision = EduQACurriculumnRevision.query.get(revision_id)
    data = []
    for session in EduQACourseSession.query.filter(EduQACourseSession.course.has(revision_id=revision_id)).all():
        for instructor in session.instructors:
            session_detail = session.details.filter_by(staff_id=instructor.account_id).first()
            if session_detail:
                factor = session_detail.factor if session_detail.factor else 1
            else:
                factor = 1
            d = {'course': session.course.en_code,
                 'instructor': instructor.account.personal_info.fullname,
                 'seconds': session.total_seconds * factor
                 }
            data.append(d)
    df = pd.DataFrame(data)
    sum_hours = df.pivot_table(index='instructor',
                               columns='course',
                               values='seconds',
                               aggfunc='sum',
                               margins=True).apply(lambda x: (x // 3600) / 40.0).fillna('')
    return render_template('eduqa/QA/mtc/summary_hours_all_courses.html',
                           sum_hours=sum_hours,
                           revision_id=revision_id)


@edu.route('/qa/teaching-hours-summary')
@login_required
def teaching_hours_index():
    records = []
    for rev in EduQACurriculumnRevision.query.all():
        records.append(rev)
    return render_template('eduqa/QA/teaching_hours_index.html', records=records)


@edu.route('/qa/revisions/<int:revision_id>/summary/yearly')
@login_required
def show_hours_summary_by_year(revision_id):
    year = request.args.get('year', type=int)
    revision = EduQACurriculumnRevision.query.get(revision_id)
    data = []
    all_years = EduQACourseSession.query.filter(EduQACourseSession.course.has(revision_id=revision_id)) \
        .with_entities(extract('year', EduQACourseSession.start)).distinct()
    all_years = sorted([int(y[0]) for y in all_years])
    if all_years:
        if not year:
            year = all_years[0]
        for session in EduQACourseSession.query.filter(EduQACourseSession.course.has(revision_id=revision_id)) \
                .filter(extract('year', EduQACourseSession.start) == year):
            for instructor in session.instructors:
                session_detail = session.details.filter_by(staff_id=instructor.account_id).first()
                if session_detail:
                    factor = session_detail.factor if session_detail.factor else 1
                else:
                    factor = 1
                d = {'course': session.course.en_code,
                     'instructor': instructor.account.personal_info.fullname,
                     'seconds': session.total_seconds * factor
                     }
                data.append(d)
        df = pd.DataFrame(data)
        sum_hours = df.pivot_table(index='instructor',
                                   columns='course',
                                   values='seconds',
                                   aggfunc='sum',
                                   margins=True).apply(lambda x: (x // 3600)).fillna('')
        return render_template('eduqa/QA/mtc/summary_hours_all_courses.html',
                               sum_hours=sum_hours,
                               year=year,
                               years=all_years,
                               revision=revision,
                               revision_id=revision_id)
    return 'No data available.'


@edu.route('/qa/backoffice/students', methods=['GET', 'POST'])
@login_required
def manage_student_list():
    form_data = request.form
    revision_id = request.args.get('revision_id', type=int)
    if request.method == 'POST':
        program_id = form_data.get('program_id')
        curriculum_id = form_data.get('curriculum_id')
        revision_id = form_data.get('revision_id')
        if program_id and curriculum_id and revision_id:
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('eduqa.list_all_courses', revision_id=revision_id)
            return resp
    return render_template('eduqa/QA/backoffice/student_list_index.html', revision_id=revision_id)


@edu.route('/qa/backoffice/revisions/<int:revision_id>/courses')
@login_required
def list_all_courses(revision_id):
    revision = EduQACurriculumnRevision.query.get(revision_id)
    return render_template('eduqa/QA/backoffice/course_list.html', revision=revision)


@edu.route('/htmx/qa/programs', methods=['GET', 'POST'])
@login_required
def htmx_programs():
    form_data = request.form
    program_id = int(form_data.get('program_id')) if form_data.get('program_id') else None
    curriculum_id = int(form_data.get('curriculum_id')) if form_data.get('curriculum_id') else None
    revision_id = int(form_data.get('revision_id')) if form_data.get('revision_id') else None
    template = ''
    selector = request.headers.get('HX-Trigger')
    if selector == 'program-select':
        revision_id = request.args.get('revision_id', type=int)
        if not program_id and revision_id:
            rev = EduQACurriculumnRevision.query.get(revision_id)
            curr = rev.curriculum
            prog = curr.program
        else:
            prog = EduQAProgram.query.get(program_id) if program_id else EduQAProgram.query.first()
            curr = prog.curriculums[0] if prog.curriculums else None
            rev = curr.revisions[0] if curr and curr.revisions else None
    if selector == 'curriculum-select':
        curr = EduQACurriculum.query.get(curriculum_id)
        prog = EduQAProgram.query.get(program_id)
        rev = curr.revisions[0] if curr.revisions else None
    if selector == 'revision-select':
        rev = EduQACurriculumnRevision.query.get(revision_id)
        curr = rev.curriculum
        prog = curr.program

    for p in EduQAProgram.query:
        selected = 'selected' if p.id == prog.id else ''
        template += f'<option value={p.id} {selected}>{p.name}</option>'

    template += '<select id="curriculum-select" name="curriculum_id" hx-swap-oob="true" hx-post="{}" hx-trigger="change">' \
        .format(url_for('eduqa.htmx_programs'))
    for c in prog.curriculums:
        selected = 'selected' if curr and c.id == curr.id else ''
        template += f'<option value={c.id} {selected}>{c.th_name}</option>'
    template += '</select>'

    template += '<select id="revision-select" name="revision_id" hx-swap-oob="true" hx-post="{}" hx-trigger="change">' \
        .format(url_for('eduqa.htmx_programs'))
    if curr and curr.revisions:
        for r in curr.revisions:
            selected = 'selected' if rev and r.id == rev.id else ''
            template += f'<option value={r.id} {selected}>{r.revision_year.year + 543}</option>'
    template += '</select>'

    resp = make_response(template)
    if rev:
        resp.headers['HX-Trigger-After-Swap'] = json.dumps(
            {'reloadDataTable':
                {
                    'url': url_for('eduqa.get_all_courses_for_the_revision', revision_id=rev.id)
                }
            })
    return resp


@edu.route('/api/revisions/courses')
@edu.route('/api/revisions/<int:revision_id>/courses')
@login_required
def get_all_courses_for_the_revision(revision_id=None):
    data = []
    if revision_id:
        revision = EduQACurriculumnRevision.query.get(revision_id)
        for course in revision.courses:
            grade_reports = 0
            for en in course.enrollments:
                if en.latest_grade_record:
                    if en.latest_grade_record.grade and en.latest_grade_record.submitted_at:
                        grade_reports += 1
            data.append({
                'th_code': f'{course.th_code} ({course.en_code})',
                'th_name': course.th_name,
                'en_name': course.en_name,
                'student_year': course.student_year,
                'semester': course.semester,
                'academic_year': course.academic_year,
                'enrollments': len(course.enrollments),
                'grade_reports': grade_reports,
                'id': course.id,
            })
    return {'data': data}


@edu.route('/courses/<int:course_id>/enrollments', methods=['GET', 'POST'])
@education_permission.require()
@login_required
def list_all_enrollments(course_id):
    course = EduQACourse.query.get(course_id)
    return render_template('eduqa/QA/backoffice/enrollments.html', course=course)


@edu.route('/revisions/<int:revision_id>/students', methods=['POST', 'GET'])
@login_required
def upload_students(revision_id):
    form = StudentUploadForm()
    revision = EduQACurriculumnRevision.query.get(revision_id)
    if form.validate_on_submit():
        f = form.upload_file.data
        df = pd.read_excel(f, skiprows=3, engine='openpyxl')
        if request.args.get('preview', 'no') == 'yes':
            en_code = df['Subject Code'][0]
            course = EduQACourse.query.filter_by(en_code=en_code,
                                                 academic_year=form.academic_year.data,
                                                 revision_id=revision_id).first()
            create_class = 'It will be created per your request.' if form.create_class.data else 'It will not be created.'
            template = ''
            if not course:
                template += f'<h1 class="title is-size-4 has-text-danger">{en_code} for year {form.academic_year.data} does not exists. {create_class}</h1>'
            else:
                template += f'<h1 class="title is-size-4 has-text-info">Subject code={en_code} for year {form.academic_year.data} exists.</h1>'
            template += df.to_html()
            return template
        else:
            row = df.iloc[0]
            course = EduQACourse.query.filter_by(en_code=row[2],
                                                 academic_year=form.academic_year.data,
                                                 revision_id=revision_id).first()
            if not course:
                if form.create_class.data:
                    course = EduQACourse(en_code=row[2],
                                         th_code=row[2],
                                         en_name=row[4],
                                         th_name=row[5],
                                         student_year=form.student_year.data,
                                         semester=form.semester.data,
                                         revision_id=revision_id,
                                         academic_year=form.academic_year.data,
                                         creator=current_user,
                                         )
                    db.session.add(course)
            enrollments = []
            new_students = 0
            for idx, row in df.iterrows():
                if not pd.isna(row[1]):
                    student = EduQAStudent.query.filter_by(student_id=row[1]).first()
                    if not student:
                        student = EduQAStudent(
                            student_id=row[1],
                            en_title=row[7],
                            en_name=row[8],
                            th_title=row[9],
                            th_name=row[10],
                            status=row[11]
                        )
                        db.session.add(student)
                        new_students += 1
                    enrollments.append(student)
            db.session.commit()
            new_enrolls = 0
            for student in enrollments:
                enroll_ = EduQAEnrollment.query.filter_by(student=student, course=course).first()
                if not enroll_:
                    EduQAEnrollment(student=student, course=course)
                    new_enrolls += 1
                    db.session.add(course)
            db.session.commit()
            flash(f'{new_students} students have been uploaded and {new_enrolls} enrolled to the course.', 'success')
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('eduqa.upload_students', revision_id=revision_id)
            return resp
    if form.errors:
        return '<h1 class="title is-size-4 has-text-danger">Data file is required.</h1>'
    return render_template('eduqa/QA/backoffice/student_list_upload_form.html',
                           form=form, revision_id=revision_id, revision=revision)


@edu.route('/courses/<int:course_id>/grade', methods=['POST', 'GET'])
@login_required
def upload_grades(course_id):
    form = StudentGradeReportUploadForm()
    course = EduQACourse.query.get(course_id)
    if form.validate_on_submit():
        f = form.upload_file.data
        df = pd.read_excel(f, sheet_name='Sheet1')
        if request.args.get('preview', 'no') == 'yes':
            template = ''
            template += df.to_html()
            return template
        else:
            for idx, row in df.iterrows():
                student = EduQAStudent.query.filter_by(student_id=row[0]).first()
                if student:
                    enrollment = EduQAEnrollment.query.filter_by(student=student, course_id=course.id).first()
                    if enrollment:
                        grade_report = EduQAStudentGradeReport(enrollment=enrollment,
                                                               grade=row[2],
                                                               creator=current_user,
                                                               )
                        db.session.add(grade_report)
                else:
                    print(f'Student with ID={row[0]} is not found.')
            db.session.commit()
            flash(f'Grade have been reported.', 'success')
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('eduqa.upload_grades', course_id=course_id)
            return resp
    if form.errors:
        return '<h1 class="title is-size-4 has-text-danger">Data file is required.</h1>'
    return render_template('eduqa/QA/student_grade_upload_form.html',
                           form=form, course=course)


@edu.route('/courses/<int:course_id>/grades/submit', methods=['POST'])
@login_required
def submit_grades(course_id):
    for en in EduQAEnrollment.query.filter_by(course_id=course_id):
        if en.latest_grade_record:
            if en.latest_grade_record.grade and not en.latest_grade_record.submitted_at:
                en.latest_grade_record.submitted_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(en)
    db.session.commit()
    flash('Grades have been submitted.', 'success')
    resp = make_response()
    resp.headers['HX-Redirect'] = url_for('eduqa.upload_grades', course_id=course_id)
    return resp


@edu.route('/courses/<int:course_id>/students/download', methods=['POST', 'GET'])
@login_required
def download_students(course_id):
    name_only = request.args.get('nameonly', 'false')
    course = EduQACourse.query.get(course_id)
    data = []
    for student in course.students:
        if name_only == 'false':
            data.append({
                'studentID': student.student_id,
                'name': f'{student.th_title}{student.th_name}',
                'grade': '',
            })
        elif name_only == 'true':
            data.append({
                'studentID': student.student_id,
                'th_title': f'{student.th_title}',
                'th_name': f'{student.th_name}',
                'en_title': f'{student.en_title.upper()}',
                'en_name': f'{student.en_name}',
            })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    suffix = 'grades' if name_only == 'false' else 'students'
    return send_file(output, download_name=f'{course.en_code}_{suffix}.xlsx')


@edu.route('/courses/<int:course_id>/students/show', methods=['GET'])
@login_required
def show_students(course_id):
    course = EduQACourse.query.get(course_id)
    data = []
    for student in course.students:
        data.append({
            'studentID': student.student_id,
            'คำนำหน้า': f'{student.th_title}',
            'ชื่อ': f'{student.th_name}',
            'Title': f'{student.en_title.upper()}',
            'Name': f'{student.en_name}',
        })

    df = pd.DataFrame(data)
    if request.args.get('hide') is None:
        url = url_for('eduqa.show_students', course_id=course_id, hide='true')
        return df.to_html() + f'<a class="button is-small is-info is-rounded" hx-target="#student-list" hx-get="{url}" hx-swap-oob="true" id="hide-btn"><span class="icon"><i class="fas fa-chevron-up"></i></span><span>hide</span></a>'
    else:
        url = url_for('eduqa.show_students', course_id=course_id)
        template = f'<a class="button is-info is-small is-rounded" hx-target="#student-list" hx-get="{url}" hx-swap-oob="true" id="hide-btn"><span class="icon"><i class="fas fa-chevron-down"></i></span><span>show</span></a>'
        resp = make_response(template)
        return resp


@edu.route('/backoffice/courses/<int:course_id>/grades/download')
@education_permission.require()
@login_required
def download_grade_report(course_id):
    course = EduQACourse.query.get(course_id)
    data = []
    for en in course.enrollments:
        if en.latest_grade_record and en.latest_grade_record.submitted_at:
            grade_report = en.latest_grade_record.grade or None
        else:
            grade_report = None
        data.append({
            'studentID': en.student.student_id,
            'grade': grade_report,
        })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name=f'{course.en_code}_grades.xlsx')


@edu.route('/courses/<int:course_id>/enrollments/<int:enroll_id>/grade/edit', methods=['PATCH', 'GET'])
@login_required
def edit_grade_report(course_id, enroll_id):
    form = StudentGradeEditForm()
    course = EduQACourse.query.get(course_id)
    enrollment = EduQAEnrollment.query.get(enroll_id)
    if course.grading_scheme:
        form.grade.choices = [('', 'No grade')] + [(c.symbol, c.symbol) for c in course.grading_scheme.items]
    else:
        form.grade.choices = [('', 'No grade')] + [(c.symbol, c.symbol) for c in EduQAGradingSchemeItem.query]

    if enrollment.latest_grade_record:
        form.grade.default = enrollment.latest_grade_record.grade

    if request.method == 'PATCH':
        grade_record = EduQAStudentGradeReport(grade=form.grade.data,
                                               enrollment=enrollment,
                                               updater=current_user,
                                               creator=current_user,
                                               )
        db.session.add(grade_record)
        db.session.commit()
        template = f'''
        <td>{enrollment.student.student_id}</td>
        <td>{enrollment.student.th_name}</td>
        <td>{grade_record.grade or 'No grade'}</td>
        <td>ยังไม่ได้ส่ง</td>
        <td>
            <a hx-get="{url_for('eduqa.edit_grade_report', course_id=course.id, enroll_id=enrollment.id)}"
               hx-swap="innerHTML"
               hx-target="#grade-edit-modal-container"
            >
                <span class="icon">
                    <i class="fa-solid fa-pencil"></i>
                </span>
            </a>
        </td>
        '''
        print(template)
        resp = make_response(template)
        resp.headers['HX-Trigger-After-Swap'] = 'closeModal'
        resp.headers['HX-Reswap'] = 'innerHTML'
        resp.headers['HX-Retarget'] = f'#grade-record-{enroll_id}'
        return resp

    return render_template('eduqa/partials/grade_edit_form.html',
                           form=form, course_id=course_id, enroll_id=enroll_id)


@edu.route('/backoffice/courses/<int:course_id>/grades')
@education_permission.require()
@login_required
def show_grade_report(course_id):
    course = EduQACourse.query.get(course_id)
    grade_counts = defaultdict(int)
    for en in course.enrollments:
        if en.latest_grade_record and en.latest_grade_record.submitted_at:
            grade_report = en.latest_grade_record.grade or 'No grade'
        else:
            grade_report = 'No grade'
        grade_counts[grade_report] += 1

    if course.grading_scheme:
        grade_items = [item.symbol for item in course.grading_scheme.items]
    else:
        grade_items = sorted([symbol or 'No grade' for symbol in grade_counts.keys()])

    return render_template('eduqa/partials/student_grade_modal.html',
                           course=course, grade_items=grade_items, grade_counts=grade_counts)


@edu.route('/courses/<int:course_id>/import')
@login_required
def import_course_data(course_id):
    course = EduQACourse.query.get(course_id)
    return render_template('eduqa/partials/course_data_import.html', course=course)


@edu.route('/coures/<int:course_id>/instructor-evaluation')
def instructor_evaluation(course_id):
    course = EduQACourse.query.get(course_id)
    return render_template('eduqa/QA/instructor_evaluation.html', course=course)


@edu.route('/courses/<int:course_id>/instructors/<int:instructor_id>/sessions')
def list_instructor_sessions(course_id, instructor_id):
    instructor = EduQAInstructor.query.get(instructor_id)
    return render_template('eduqa/partials/instructor_topics.html',
                           instructor=instructor, course_id=course_id)


@edu.route('/courses/<int:course_id>/instructors/<int:instructor_id>/evaluation-form', methods=['GET', 'POST'])
def instructor_evaluation_form(course_id, instructor_id):
    categories = EduQAInstructorEvaluationCategory.query.all()
    choices = EduQAInstructorEvaluationChoice.query.order_by(EduQAInstructorEvaluationChoice.score.desc())
    if request.method == 'POST':
        form = request.form
        eval = EduQAInstructorEvaluation(course_id=course_id, instructor_id=instructor_id)
        for field, value in form.items():
            if field.startswith('item'):
                _, item_id = field.split('-')
                eval_result = EduQAInstructorEvaluationResult(evaluation_item_id=int(item_id), evaluation=eval)
                eval_result.choice_id = int(value)
                db.session.add(eval_result)
            elif field == 'suggestion':
                eval.suggestion = value
        db.session.add(eval)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Trigger'] = 'closeModal'
        return resp
    return render_template('eduqa/partials/instructor_evaluation_form.html',
                           categories=categories,
                           choices=choices,
                           course_id=course_id,
                           instructor_id=instructor_id)


@edu.route('/courses/<int:course_id>/instructors/<int:instructor_id>/evaluation-result')
@login_required
def instructor_evaluation_result(course_id, instructor_id):
    course = EduQACourse.query.get(course_id)
    categories = EduQAInstructorEvaluationCategory.query.all()
    return render_template('eduqa/partials/instructor_evaluation_result.html',
                           categories=categories, course=course, instructor_id=instructor_id)


@edu.route('/courses/search')
@login_required
def search_course():
    course_code = request.args.get('course_code')
    source = request.args.get('source')
    if course_code:
        courses = EduQACourse.query.filter(or_(EduQACourse.en_code.like('%{}%'.format(course_code)),
                                               EduQACourse.th_code.like('%{}%'.format(course_code))))
        template = '<table class="table is-fullwidth">'
        template += '<thead><th>Course</th><th>Semester</th><th>Year</th></thead>'
        for c in courses:
            if source == 'backoffice':
                course_url = url_for('eduqa.show_course_detail_public', course_id=c.id, source=source)
            else:
                course_url = url_for('eduqa.show_course_detail', course_id=c.id)
            template += '<tr><td><a href="{}">{} ({})</a></td><td>{}</td><td>{}</td>'.format(course_url,
                                                                                             c.th_name,
                                                                                             c.en_code,
                                                                                             c.semester,
                                                                                             c.academic_year)
        template += '</table>'
        return template
    return ''


sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
bold_sarabun_font = TTFont('SarabunBold', 'app/static/fonts/THSarabunNewBold.ttf')
pdfmetrics.registerFont(sarabun_font)
pdfmetrics.registerFont(bold_sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun', fontSize=14))
style_sheet.add(ParagraphStyle(name='ThaiStyleSmall', fontName='Sarabun', fontSize=9))
style_sheet.add(ParagraphStyle(name='ThaiStylePageHeader',
                               fontName='Sarabun',
                               fontSize=9,
                               borderWidth=0.5,
                               borderColor='#000000',
                               borderPadding=(7, 2, 10)
                               ))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', fontSize=14, alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', fontSize=14, alignment=TA_CENTER))
style_sheet.add(ParagraphStyle(name='ThaiStyleHeaderCenter',
                               fontName='SarabunBold',
                               fontSize=16,
                               leading=18,
                               alignment=TA_CENTER))
style_sheet.add(ParagraphStyle(name='ThaiStyleTableHeaderCenter',
                               fontName='SarabunBold',
                               fontSize=14,
                               leading=15,
                               alignment=TA_CENTER))


@edu.route('/courses/<int:course_id>/export-pdf')
@login_required
def export_pdf(course_id):
    course = EduQACourse.query.get(course_id)
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 30, 30)

    def _header_footer(canvas, doc):
        canvas.saveState()
        # Header
        header = Paragraph((f'{course.revision.curriculum} ระดับ {course.revision.curriculum.program.degree}'
                            f'<br/>ชื่อรายวิชา {course.th_name} รหัส {course.th_code} ปรับปรุงล่าสุดวันที่ {updated_date}'
                            f'<br/>คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'),
                           style_sheet['ThaiStylePageHeader'])
        w, h = header.wrap(doc.width, doc.topMargin)
        header.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h)

        # Footer
        footer = Paragraph('This is a multi-line footer.  It goes on every page.   ' * 5, style_sheet['ThaiStyle'])
        w, h = footer.wrap(doc.width, doc.bottomMargin)
        footer.drawOn(canvas, doc.leftMargin, h)

        logo_image = ImageReader('app/static/img/mu-watermark.png')
        canvas.drawImage(logo_image, 140, 265, mask='auto')

        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer,
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=20,
                            bottomMargin=10,
                            )
    data = []
    affiliation = '''<para align=center><font size=10>
            คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/></font></para>
            '''
    program_info = f'''<para align=left>
    {course.revision.curriculum.program} สาขา {course.revision.curriculum}
    </para>
    '''
    course_name_th = f'''{course.th_name} ({course.th_code})'''
    course_name_en = f'''{course.en_name} ({course.en_code})'''

    updated_date = arrow.get(course.updated_at.astimezone(bangkok)).format(fmt='DD MMMM YYYY', locale='th-th')
    revision_info = f'''<font size=16>วันที่ {updated_date}</font>'''

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ])

    data.append(logo)
    data.append(Paragraph(affiliation, style=style_sheet['ThaiStyle']))

    data.append(Paragraph('รายละเอียดของรายวิชา', style=style_sheet['ThaiStyleHeaderCenter']))
    data.append(Paragraph('หมวดที่ 1 ข้อมูลทั่วไป', style=style_sheet['ThaiStyleHeaderCenter']))

    doc.build(data, onLaterPages=_header_footer, onFirstPage=_header_footer)
    buffer.seek(0)
    return send_file(buffer, download_name=f'{course.en_code}_มม3.pdf')


class PageNumCanvas(canvas.Canvas):
    """
    http://code.activestate.com/recipes/546511-page-x-of-y-with-reportlab/
    http://code.activestate.com/recipes/576832/
    """

    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        """Constructor"""
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []

    # ----------------------------------------------------------------------
    def showPage(self):
        """
        On a page break, add information to the list
        """
        self.pages.append(dict(self.__dict__))
        self._startPage()

    # ----------------------------------------------------------------------
    def save(self):
        """
        Add the page number to each page (page x of y)
        """
        page_count = len(self.pages)

        for page in self.pages:
            self.__dict__.update(page)
            self.draw_page_number(page_count)
            canvas.Canvas.showPage(self)

        canvas.Canvas.save(self)

    # ----------------------------------------------------------------------
    def draw_page_number(self, page_count):
        """
        Add the page number
        """
        page = "%s/%s" % (self._pageNumber, page_count)
        self.setFont("Sarabun", 12)
        self.drawRightString(195 * mm, 290 * mm, page)


@edu.route('/courses/<int:course_id>/export-grade-pdf')
@login_required
def export_grade_pdf(course_id):
    course = EduQACourse.query.get(course_id)
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 30, 30)

    def _header_footer(canvas, doc):
        canvas.saveState()
        # Footer
        print_datetime = arrow.now('Asia/Bangkok').format(fmt='DD MMMM YYYY HH:MM:SS', locale='th-th')
        footer = Paragraph(
            f'พิมพ์เมื่อ {print_datetime}&nbsp&nbsp&nbsp;ตรวจสอบและรับรองโดย {current_user.fullname} ..............................................',
            style_sheet['ThaiStyle'])
        w, h = footer.wrap(doc.width, doc.bottomMargin)
        footer.drawOn(canvas, doc.leftMargin, h)

        logo_image = ImageReader('app/static/img/mu-watermark.png')
        canvas.drawImage(logo_image, 140, 265, mask='auto')

        canvas.restoreState()

    items = [[Paragraph('ลำดับ', style=style_sheet['ThaiStyleTableHeaderCenter']),
              Paragraph('รหัส', style=style_sheet['ThaiStyleTableHeaderCenter']),
              Paragraph('คำนำหน้า', style=style_sheet['ThaiStyleTableHeaderCenter']),
              Paragraph('ชื่อ', style=style_sheet['ThaiStyleTableHeaderCenter']),
              Paragraph('ผลการเรียน', style=style_sheet['ThaiStyleTableHeaderCenter']),
              ]]
    grade_counts = defaultdict(int)
    for n, en in enumerate(course.enrollments, start=1):
        if en.latest_grade_record and en.latest_grade_record.submitted_at:
            items.append([
                Paragraph(f'<para align=center>{n}</para>', style=style_sheet['ThaiStyle']),
                Paragraph(f'<para align=center>{en.student.student_id}</para>', style=style_sheet['ThaiStyle']),
                Paragraph(f'<para align=center>{en.student.th_title}</para>', style=style_sheet['ThaiStyle']),
                Paragraph(en.student.th_name, style=style_sheet['ThaiStyle']),
                Paragraph(f'<para align=center>{en.latest_grade_record.grade or "No grade"}</para>',
                          style=style_sheet['ThaiStyle'])
            ])
            grade_report = en.latest_grade_record.grade or 'No grade'
        else:
            items.append([
                Paragraph(f'<para align=center>{n}</para>', style=style_sheet['ThaiStyle']),
                Paragraph(f'<para align=center>{en.student.student_id}</para>', style=style_sheet['ThaiStyle']),
                Paragraph(f'<para align=center>{en.student.th_title}</para>', style=style_sheet['ThaiStyle']),
                Paragraph(en.student.th_name, style=style_sheet['ThaiStyle']),
                Paragraph(f'<para align=center>"No grade"</para>', style=style_sheet['ThaiStyle'])
            ])
            grade_report = 'No grade'
        grade_counts[grade_report] += 1

    if course.grading_scheme:
        grade_items = [item.symbol for item in course.grading_scheme.items]
    else:
        grade_items = sorted([symbol or 'No grade' for symbol in grade_counts.keys()])
    item_table = Table(items, colWidths=[40, 60, 60, 200, 70], repeatRows=1)
    item_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, 0), 0.25, colors.black),
        ('BOX', (0, 0), (0, -1), 0.25, colors.black),
        ('BOX', (1, 0), (1, -1), 0.25, colors.black),
        ('BOX', (2, 0), (2, -1), 0.25, colors.black),
        ('BOX', (3, 0), (3, -1), 0.25, colors.black),
        ('BOX', (4, 0), (4, -1), 0.25, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
    ]))
    item_table.setStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])

    grade_count_items = [[
        Paragraph('สัญลักษณ์', style=style_sheet['ThaiStyleTableHeaderCenter']),
        Paragraph('จำนวน', style=style_sheet['ThaiStyleTableHeaderCenter']),
    ]]
    for s in grade_items:
        grade_count_items.append([
            Paragraph(f'<para align=center>{s}</para>', style=style_sheet['ThaiStyle']),
            Paragraph(f'<para align=center>{grade_counts[s]}</para>', style=style_sheet['ThaiStyleNumber']),
        ])
    grade_count_item_table = Table(grade_count_items, colWidths=[70, 60], repeatRows=1)
    grade_count_item_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, 0), 0.25, colors.black),
        ('BOX', (0, 0), (0, -1), 0.25, colors.black),
        ('BOX', (1, 0), (1, -1), 0.25, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
    ]))
    grade_count_item_table.setStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer,
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=20,
                            bottomMargin=40,
                            )
    data = [
        Paragraph(f'รายงานผลการเรียนวิชา{course.th_name}', style=style_sheet['ThaiStyleHeaderCenter']),
        Paragraph(f'{course.en_name}&nbsp({course.en_code})', style=style_sheet['ThaiStyleHeaderCenter']),
        Paragraph(f'ปีการศึกษา&nbsp;{course.academic_year}', style=style_sheet['ThaiStyleHeaderCenter']),
        Paragraph(f'{course.revision}', style=style_sheet['ThaiStyleHeaderCenter']),
        Spacer(1, 12),
        grade_count_item_table,
        Spacer(1, 12),
        item_table,
    ]
    doc.build(data, onLaterPages=_header_footer, onFirstPage=_header_footer, canvasmaker=PageNumCanvas)
    buffer.seek(0)
    return send_file(buffer, download_name=f'{course.en_code}_grade.pdf')


@edu.route('/courses/<int:course_id>/students/<int:student_id>', methods=['DELETE'])
@login_required
def withdraw_enrollment(course_id, student_id):
    enrollment = EduQAEnrollment.query.filter_by(course_id=course_id, student_id=student_id).first()
    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        flash('Enrollment has been withdrawn', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    else:
        resp = make_response()
        return resp, 400
