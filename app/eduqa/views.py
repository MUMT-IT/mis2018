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
@login_required
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
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(course)
            course.updater = current_user
            course.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(course)
            db.session.commit()
            flash(u'บันทึกข้อมูลรายวิชาเรียบร้อย', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            flash(u'เกิดความผิดพลาดบางประการ กรุณาตรวจสอบข้อมูล', 'warning')
    return render_template('eduqa/QA/course_edit.html', form=form, revision_id=course.revision_id)


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
    if request.method == 'POST':
        program_id = form_data.get('program_id')
        curriculum_id = form_data.get('curriculum_id')
        revision_id = form_data.get('revision_id')
        if program_id and curriculum_id and revision_id:
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('eduqa.list_all_courses', revision_id=revision_id)
            return resp
    return render_template('eduqa/QA/backoffice/student_list_index.html')


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
    for prog in EduQAProgram.query:
        selected = 'selected' if prog.id == program_id else ''
        template += f'<option value={prog.id} {selected}>{prog.name}</option>'

    if program_id is None:
        prog = EduQAProgram.query.first()
    else:
        prog = EduQAProgram.query.get(program_id)

    template += '<select id="curriculum-select" name="curriculum_id" hx-swap-oob="true" hx-post="{}" hx-trigger="change">' \
        .format(url_for('eduqa.htmx_programs'))
    for curr in prog.curriculums:
        selected = 'selected' if curr.id == curriculum_id else ''
        template += f'<option value={curr.id} {selected}>{curr.th_name}</option>'
    template += '</select>'

    if curriculum_id:
        curr = EduQACurriculum.query.get(curriculum_id)
        if curr not in prog.curriculums:
            curr = prog.curriculums[0]
            revision_id = None
    else:
        curr = prog.curriculums[0]
        revision_id = None

    template += '<select id="revision-select" name="revision_id" hx-swap-oob="true" hx-post="{}" hx-trigger="change">' \
        .format(url_for('eduqa.htmx_programs'))

    if revision_id:
        rev = EduQACurriculumnRevision.query.get(revision_id)
    else:
        rev = curr.revisions[0]

    for r in curr.revisions:
        if r.id == revision_id:
            selected = 'selected'
        template += f'<option value={r.id} {selected}>{r.revision_year.year + 543}</option>'
    template += '</select>'

    upload_url = url_for('eduqa.upload_students', revision_id=rev.id)
    template += f'<a href="{upload_url}" class="button is-link" id="upload-btn" hx-swap-oob="true">Upload รายชื่อ</a>'

    resp = make_response(template)
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
        df = pd.read_excel(f, skiprows=2, sheet_name='Sheet1')
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
    course = EduQACourse.query.get(course_id)
    data = []
    for student in course.students:
        data.append({
            'studentID': student.student_id,
            'name': f'{student.th_title}{student.th_name}',
            'grade': '',
        })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name=f'{course.en_code}_grades.xlsx')


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
    if course_code:
        courses = EduQACourse.query.filter(or_(EduQACourse.en_code.like('%{}%'.format(course_code)),
                                               EduQACourse.th_code.like('%{}%'.format(course_code))))
        template = '<table class="table is-fullwidth">'
        template += '<thead><th>Course</th><th>Year</th></thead>'
        for c in courses:
            course_url = url_for('eduqa.show_course_detail', course_id=c.id)
            template += '<tr><td><a href="{}">{} ({})</a></td><td>{}</td>'.format(course_url,
                                                                                  c.th_name,
                                                                                  c.en_code,
                                                                                  c.academic_year)
        template += '</table>'
        return template
    return ''
