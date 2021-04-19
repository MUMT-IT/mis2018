# -*- coding:utf-8 -*-
from datetime import datetime

from flask import render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import make_transient

from . import eduqa_bp as edu
from forms import *
from ..staff.models import StaffPersonalInfo

from pytz import timezone

localtz = timezone('Asia/Bangkok')

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
    revision = EduQACurriculumnRevision.query.get(revision_id)
    return render_template('eduqa/QA/curriculum_revision_detail.html', revision=revision)


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
            course.created_at = localtz.localize(datetime.now())
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
            course.updated_at = localtz.localize(datetime.now())
            db.session.add(course)
            db.session.commit()
            flash(u'บันทึกข้อมูลรายวิชาเรียบร้อย', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            flash(u'เกิดความผิดพลาดบางประการ กรุณาตรวจสอบข้อมูล', 'warning')
    return render_template('eduqa/QA/course_edit.html', form=form, revision_id=course.revision_id)


@edu.route('/qa/courses/<int:course_id>/copy', methods=['GET', 'POST'])
@login_required
def copy_course(course_id):
    course = EduQACourse.query.get(course_id)
    db.session.expunge(course)
    make_transient(course)
    course.th_name = course.th_name + '(copy)'
    course.th_code = course.th_code + '(copy)'
    course.academic_year = None
    course.id = None
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
    return render_template('eduqa/QA/course_detail.html', course=course)


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
    course.instructors.append(instructor)
    course.updater = current_user
    course.updated_at = localtz.localize(datetime.now())
    db.session.add(instructor)
    db.session.add(course)
    db.session.commit()
    flash(u'เพิ่มรายชื่อผู้สอนเรียบร้อยแล้ว', 'success')
    return redirect(url_for('eduqa.show_course_detail', course_id=course_id))


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
    course.updated_at = localtz.localize(datetime.now())
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
        if form.validate_on_submit():
            new_session = EduQACourseSession()
            form.populate_obj(new_session)
            new_session.course = course
            new_session.start = localtz.localize(new_session.start)
            new_session.end = localtz.localize(new_session.end)
            course.updated_at = localtz.localize(datetime.now())
            course.updater = current_user
            db.session.add(new_session)
            db.session.commit()
            flash(u'เพิ่มรายการสอนเรียบร้อยแล้ว', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            flash(u'เกิดปัญหาในการบันทึกข้อมูล', 'warning')
    return render_template('eduqa/QA/session_edit.html', form=form, course=course)


@edu.route('/qa/courses/<int:course_id>/sessions/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_session(course_id, session_id):
    course = EduQACourse.query.get(course_id)
    a_session = EduQACourseSession.query.get(session_id)
    InstructorForm = create_instructors_form(course)
    form = InstructorForm(obj=a_session)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(a_session)
            a_session.course = course
            course.updater = current_user
            a_session.start = localtz.localize(a_session.start)
            a_session.end = localtz.localize(a_session.end)
            course.updated_at = localtz.localize(datetime.now())
            db.session.add(a_session)
            db.session.commit()
            flash(u'แก้ไขรายการสอนเรียบร้อยแล้ว', 'success')
            return redirect(url_for('eduqa.show_course_detail', course_id=course.id))
        else:
            flash(u'เกิดปัญหาในการบันทึกข้อมูล', 'warning')
    return render_template('eduqa/QA/session_edit.html', form=form, course=course)


@edu.route('/qa/hours/<int:instructor_id>')
@login_required
def show_hours_summary(instructor_id):
    instructor = EduQAInstructor.query.get(instructor_id)
    return render_template('eduqa/QA/hours_summary.html', instructor=instructor)
