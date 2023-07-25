# -*- coding:utf-8 -*-
import pandas as pd

import arrow
from flask import render_template, request, flash, redirect, url_for, session, jsonify, make_response
from flask_login import current_user, login_required
from sqlalchemy.orm import make_transient
from sqlalchemy import extract

from . import eduqa_bp as edu
from app.eduqa.forms import *
from ..staff.models import StaffPersonalInfo

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
                           admin=admin,
                           instructor_role=instructor_role)


@edu.route('/qa/courses/<int:course_id>/instructors/add')
@login_required
def add_instructor(course_id):
    academics = StaffPersonalInfo.query.filter_by(academic_staff=True)
    return render_template('eduqa/QA/instructor_add.html', course_id=course_id, academics=academics)


@edu.route('/qa/courses/<int:course_id>/instructors/add/<int:account_id>')
@login_required
def add_instructor_to_list(course_id, account_id):
    course = EduQACourse.query.get(course_id)
    instructor = EduQAInstructor.query.filter_by(account_id=account_id).first()
    if not instructor:
        instructor = EduQAInstructor(account_id=account_id)
    course.course_instructor_associations.append(EduQACourseInstructorAssociation(instructor=instructor))
    course.updater = current_user
    course.updated_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(instructor)
    db.session.add(course)
    db.session.commit()
    flash(u'เพิ่มรายชื่อผู้สอนเรียบร้อยแล้ว', 'success')
    return redirect(url_for('eduqa.show_course_detail', course_id=course_id))


@edu.route('/qa/courses/<int:course_id>/instructors/roles/assignment', methods=['GET', 'POST'])
@login_required
def assign_roles(course_id):
    course = EduQACourse.query.get(course_id)
    form = EduCourseInstructorRoleForm()
    if form.validate_on_submit():
        for form_field in form.roles:
            course_inst = EduQACourseInstructorAssociation.query\
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
    form = InstructorForm()
    if request.method == 'POST':
        for event_form in form.events:
            event_form.start.data = form.start.data
            event_form.end.data = form.end.data
            event_form.title.data = f'{course.en_code}'
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
    a_session = EduQACourseSession.query.get(session_id)
    InstructorForm = create_instructors_form(course)
    form = InstructorForm(obj=a_session)
    if request.method == 'POST':
        for event_form in form.events:
            if event_form.room.data:
                event_form.start.data = form.start.data
                event_form.end.data = form.end.data
                event_form.title.data = f'{course.en_code}'
        if form.validate_on_submit():
            form.populate_obj(a_session)
            a_session.course = course
            course.updater = current_user
            a_session.start = arrow.now('Asia/Bangkok').datetime
            a_session.end = arrow.now('Asia/Bangkok').datetime
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
    return render_template('eduqa/QA/session_edit.html', form=form, course=course, session_id=session_id, localtz=localtz)


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
    session_detail = EduQACourseSessionDetail.query\
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


@edu.route('/qa/revisions/<int:revision_id>/summary/hours')
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
def teaching_hours_index():
    records = []
    for rev in EduQACurriculumnRevision.query.all():
        records.append(rev)
    return render_template('eduqa/QA/teaching_hours_index.html', records=records)


@edu.route('/qa/revisions/<int:revision_id>/summary/yearly')
def show_hours_summary_by_year(revision_id):
    year = request.args.get('year', type=int)
    revision = EduQACurriculumnRevision.query.get(revision_id)
    data = []
    all_years = EduQACourseSession.query.filter(EduQACourseSession.course.has(revision_id=revision_id))\
        .with_entities(extract('year', EduQACourseSession.start)).distinct()
    all_years = sorted([int(y[0]) for y in all_years])
    if all_years:
        if not year:
            year = all_years[0]
        for session in EduQACourseSession.query.filter(EduQACourseSession.course.has(revision_id=revision_id))\
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
