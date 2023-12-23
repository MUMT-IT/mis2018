# -*- coding:utf-8 -*-
from sqlalchemy import func
from sqlalchemy.ext.associationproxy import association_proxy

from app.main import db
from app.staff.models import StaffAccount
from pytz import timezone

bangkok = timezone('Asia/Bangkok')

session_instructors = db.Table('eduqa_session_instructor_assoc',
                               db.Column('session_id', db.Integer,
                                         db.ForeignKey('eduqa_course_sessions.id')),
                               db.Column('instructor_id', db.Integer,
                                         db.ForeignKey('eduqa_course_instructors.id')),
                               )

session_assignment_instructors = db.Table('eduqa_session_assignment_instructor_assoc',
                                          db.Column('session_assignment_id', db.Integer,
                                                    db.ForeignKey('eduqa_course_assignment_sessions.id')),
                                          db.Column('instructor_id', db.Integer,
                                                    db.ForeignKey('eduqa_course_instructors.id')),
                                          )

learning_activity_assessments = db.Table('eduqa_learning_activity_assessment_assoc',
                                         db.Column('learning_activity_id', db.Integer,
                                                   db.ForeignKey('eduqa_course_learning_activities.id')),
                                         db.Column('learning_assessment_id', db.Integer,
                                                   db.ForeignKey('eduqa_course_learning_activity_assessments.id')),
                                         )

clo_plos = db.Table('eduqa_clo_plo_assoc',
                    db.Column('clo_id', db.Integer,
                              db.ForeignKey('eduqa_course_learning_outcomes.id')),
                    db.Column('instructor_id', db.Integer,
                              db.ForeignKey('eduqa_plos.id')),
                    )

course_plos = db.Table('eduqa_course_plo_assoc',
                       db.Column('course_id', db.Integer,
                                 db.ForeignKey('eduqa_courses.id')),
                       db.Column('instructor_id', db.Integer,
                                 db.ForeignKey('eduqa_plos.id')),
                       )


class EduQAStudent(db.Model):
    __tablename__ = 'eduqa_students'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column('student_id', db.Integer, unique=True, nullable=False)
    th_title = db.Column('th_title', db.String(16))
    en_title = db.Column('en_title', db.String(16))
    th_name = db.Column('th_name', db.String(255))
    en_name = db.Column('en_name', db.String(255))
    email = db.Column('email', db.String(255))
    status = db.Column(db.String(16))

    courses = association_proxy('enrollments', 'course')


class EduQAEnrollment(db.Model):
    __tablename__ = 'eduqa_student_enrollments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('eduqa_courses.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('eduqa_students.id'))
    status = db.Column(db.String(16))
    note = db.Column(db.Text())

    course = db.relationship('EduQACourse', backref=db.backref('enrollments'))
    student = db.relationship(EduQAStudent, backref=db.backref('enrollments'))

    @property
    def latest_grade_record(self):
        return self.grade_records[-1] if self.grade_records else None


class EduQAStudentGradeReport(db.Model):
    __tablename__ = 'eduqa_student_grade_reports'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('eduqa_student_enrollments.id'))
    enrollment = db.relationship(EduQAEnrollment,
                                 backref=db.backref('grade_records', order_by='EduQAStudentGradeReport.id'))
    grade = db.Column(db.String(16))
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), default=func.now())
    updater_id = db.Column('updater_id', db.ForeignKey('staff_account.id'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=func.now())
    creator_id = db.Column('creator_id', db.ForeignKey('staff_account.id'))
    submitted_at = db.Column('submitted_at', db.DateTime(timezone=True))

    creator = db.relationship(StaffAccount, foreign_keys=[creator_id])
    updater = db.relationship(StaffAccount, foreign_keys=[updater_id])


class EduQACourseInstructorAssociation(db.Model):
    __tablename__ = 'eduqa_course_instructor_assoc'

    def __init__(self, instructor=None, course=None, role=None):
        self.instructor = instructor
        self.course = course
        self.role = role

    course_id = db.Column('course_id', db.Integer,
                          db.ForeignKey('eduqa_courses.id'), primary_key=True)
    instructor_id = db.Column('instructor_id', db.Integer,
                              db.ForeignKey('eduqa_course_instructors.id'),
                              primary_key=True)
    role_id = db.Column('role_id', db.Integer,
                        db.ForeignKey('eduqa_course_instructor_roles.id'))

    course = db.relationship('EduQACourse',
                             back_populates='course_instructor_associations')
    instructor = db.relationship('EduQAInstructor')
    role = db.relationship('EduQAInstructorRole')


class EduQAProgram(db.Model):
    __tablename__ = 'eduqa_programs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False,
                     info={'label': u'ชื่อ'})
    degree = db.Column(db.String(), nullable=False,
                       info={'label': u'ระดับ',
                             'choices': (('undergraduate', 'undergraduate'),
                                         ('graudate', 'graduate'))
                             })


class EduQAPLO(db.Model):
    __tablename__ = 'eduqa_plos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column('number', db.Numeric())
    outcome = db.Column('outcome', db.Text(), nullable=False)
    revision_id = db.Column('revision_id', db.ForeignKey('eduqa_curriculum_revisions.id'))
    parent_id = db.Column('parent_id', db.ForeignKey('eduqa_plos.id'))
    sub_plos = db.relationship('EduQAPLO', backref=db.backref('parent', remote_side=[id]))
    revision = db.relationship('EduQACurriculumnRevision', backref=db.backref('plos'))

    def __str__(self):
        if self.parent_id:
            return f'Sub-PLO{self.number} {self.outcome}'
        else:
            return f'PLO{self.number} {self.outcome}'


class EduQACurriculum(db.Model):
    __tablename__ = 'eduqa_curriculums'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    program_id = db.Column(db.ForeignKey('eduqa_programs.id'),
                           )
    program = db.relationship(EduQAProgram, backref=db.backref('curriculums'))
    th_name = db.Column(db.String(), nullable=False,
                        info={'label': u'ชื่อ'})
    en_name = db.Column(db.String(), nullable=False,
                        info={'label': 'Title'})

    def __str__(self):
        return u'{} {}'.format(self.program.name, self.th_name)


class EduQACurriculumnRevision(db.Model):
    __tablename__ = 'eduqa_curriculum_revisions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    curriculum_id = db.Column(db.ForeignKey('eduqa_curriculums.id'))
    curriculum = db.relationship(EduQACurriculum,
                                 backref=db.backref('revisions'))
    revision_year = db.Column(db.Date(),
                              nullable=False,
                              info={'label': u'วันที่ปรับปรุงล่าสุด'})

    @property
    def buddhist_year(self):
        return u'{}'.format(self.revision_year.year + 543)

    def __str__(self):
        return u'{}: ปี {}'.format(self.curriculum, self.buddhist_year)


class EduQAAcademicStaff(db.Model):
    __tablename__ = 'eduqa_academic_staff'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    roles = db.Column(db.String(), info={'label': u'บทบาท',
                                         'choices': (
                                             ('staff', u'อาจารย์ประจำ'),
                                             ('head', u'ประธานหลักสูตร'),
                                             ('committee', u'ผู้รับผิดชอบหลักสูตร')
                                         )})
    curriculumn_id = db.Column(db.ForeignKey('eduqa_curriculum_revisions.id'))
    curriculumn = db.relationship(EduQACurriculumnRevision, backref=db.backref('staff'))


class EduQACourseCategory(db.Model):
    __tablename__ = 'eduqa_course_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(255), nullable=False)


class EduQACourse(db.Model):
    __tablename__ = 'eduqa_courses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    th_code = db.Column(db.String(255), nullable=False, info={'label': u'รหัส'})
    en_code = db.Column(db.String(255), nullable=False, info={'label': u'English Code'})
    th_name = db.Column(db.String(255), nullable=False, info={'label': u'ชื่อภาษาไทย'})
    en_name = db.Column(db.String(255), nullable=False, info={'label': u'English Title'})
    student_year = db.Column(db.String(), info={'label': 'ระดับ',
                                                'choices': [(c, c) for c in ('ปี 1', 'ปี 2', 'ปี 3', 'ปี 4')]})
    semester = db.Column(db.String(), info={'label': u'ภาคการศึกษา', 'choices':[(c, c) for c in ('1', '2', '3')]})
    academic_year = db.Column(db.String(), info={'label': u'ปีการศึกษา'})
    goal = db.Column(db.Text(), info={'label': 'เป้าหมายของรายวิชา'})
    objective = db.Column(db.Text(), info={'label': 'จุดประสงค์ของรายวิชา'})
    th_desc = db.Column(db.Text(), info={'label': u'คำอธิบายรายวิชา'})
    en_desc = db.Column(db.Text(), info={'label': u'Description'})
    lecture_credit = db.Column(db.Numeric(), default=0, info={'label': u'หน่วยกิตบรรยาย'})
    lab_credit = db.Column(db.Numeric(), default=0, info={'label': u'หน่วยกิตปฏิบัติ'})
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    creator_id = db.Column(db.ForeignKey('staff_account.id'))
    updater_id = db.Column(db.ForeignKey('staff_account.id'))

    creator = db.relationship(StaffAccount, foreign_keys=[creator_id])
    updater = db.relationship(StaffAccount, foreign_keys=[updater_id])

    category_id = db.Column(db.ForeignKey('eduqa_course_categories.id'))
    category = db.relationship(EduQACourseCategory,
                               backref=db.backref('courses', lazy='dynamic'))

    revision_id = db.Column(db.ForeignKey('eduqa_curriculum_revisions.id'))
    revision = db.relationship(EduQACurriculumnRevision,
                               backref=db.backref('courses', lazy='dynamic'))

    instructors = association_proxy('course_instructor_associations', 'instructor')
    course_instructor_associations = db.relationship('EduQACourseInstructorAssociation',
                                                     back_populates='course', cascade='all, delete-orphan')
    grading_scheme_id = db.Column('grading_scheme_id', db.ForeignKey('eduqa_grading_schemes.id'))
    grading_scheme = db.relationship('EduQAGradingScheme')
    grade_petition = db.Column('petition', db.Text(), info={'label': 'การอุทธรณ์'})
    grade_correction = db.Column('grade_correction', db.Text(), info={'label': 'การแก้ผลการเรียน'})
    revision_plan = db.Column('revision_plan', db.Text(), info={'label': 'การทบทวนและวางแผนปรับปรุงรายวิชา'})
    evaluation_plan = db.Column('evaluation_plan', db.Text(), info={'label': 'การจัดทำรายงานการประเมินตนเองของรายวิชา'})

    students = association_proxy('enrollments', 'student')

    @property
    def total_clo_percent(self):
        return sum([c.score_weight for c in self.outcomes])

    @property
    def credits(self):
        return self.lecture_credit + self.lab_credit

    def has_admin(self, instructor):
        for asc in self.course_instructor_associations:
            if asc.role:
                if asc.instructor == instructor and asc.role.admin:
                    return True
        return False

    def get_average_evaluation_score(self, item_id, instructor_id):
        score = 0
        number = self.get_number_evaluator(item_id, instructor_id)
        if number == 0:
            return 0.0
        else:
            for eval in self.evaluations:
                score += sum([r.choice.score for r in eval.results.filter_by(
                                evaluation_item_id=item_id)
                             .filter(EduQAInstructorEvaluationResult.evaluation.has(instructor_id=instructor_id))
                              ]
                             )
            return score / self.get_number_evaluator(item_id, instructor_id)

    def get_number_evaluator(self, item_id, instructor_id):
        number = 0
        for eval in self.evaluations:
            number += eval.results.filter_by(evaluation_item_id=item_id)\
                .filter(EduQAInstructorEvaluationResult.evaluation.has(instructor_id=instructor_id)).count()
        return number


class EduQACourseSuggestedMaterials(db.Model):
    __tablename__ = 'eduqa_course_suggested_materials'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    detail = db.Column('detail', db.Text(), nullable=False)
    course_id = db.Column('course_id', db.ForeignKey('eduqa_courses.id'))
    course = db.relationship(EduQACourse,
                             backref=db.backref('suggested_materials', cascade='all, delete-orphan'))


class EduQACourseRequiredMaterials(db.Model):
    __tablename__ = 'eduqa_course_required_materials'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    detail = db.Column('detail', db.Text(), nullable=False)
    course_id = db.Column('course_id', db.ForeignKey('eduqa_courses.id'))
    course = db.relationship(EduQACourse,
                             backref=db.backref('required_materials', cascade='all, delete-orphan'))


class EduQACourseResources(db.Model):
    __tablename__ = 'eduqa_course_resources'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    detail = db.Column('detail', db.Text(), nullable=False)
    course_id = db.Column('course_id', db.ForeignKey('eduqa_courses.id'))
    course = db.relationship(EduQACourse,
                             backref=db.backref('resources', cascade='all, delete-orphan'))


class EduQACourseLearningOutcome(db.Model):
    __tablename__ = 'eduqa_course_learning_outcomes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column('course_id', db.ForeignKey('eduqa_courses.id'))
    number = db.Column('number', db.Integer(), info={'label': 'ลำดับ'})
    detail = db.Column('detail', db.Text(), info={'label': 'รายละเอียด'})
    course = db.relationship(EduQACourse, backref=db.backref('outcomes',
                                                             cascade='all, delete-orphan'))
    score_weight = db.Column('score_weight', db.Numeric(), default=0.0, info={'label': 'สัดส่วน'})

    plos = db.relationship(EduQAPLO, backref=db.backref('clos', lazy='dynamic'), secondary=clo_plos)

    def __str__(self):
        return f'{self.course.en_code}:{self.detail}'

    @property
    def total_score_weight(self):
        return sum([pair.score_weight for pair in self.learning_activity_assessment_pairs])


class EduQAFormativeAssessment(db.Model):
    __tablename__ = 'eduqa_course_formative_assessments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    desc = db.Column('desc', db.Text(), nullable=False, info={'label': 'รายละเอียด'})
    course_id = db.Column('course_id', db.ForeignKey('eduqa_courses.id'))
    course = db.relationship(EduQACourse,
                             backref=db.backref('formative_assessments', cascade='all, delete-orphan'))

    def __str__(self):
        return self.detail


class EduQALearningActivity(db.Model):
    __tablename__ = 'eduqa_course_learning_activities'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    detail = db.Column('detail', db.String(), nullable=False)
    clo_id = db.Column('clo_id', db.ForeignKey('eduqa_course_learning_outcomes.id'))
    clo = db.relationship(EduQACourseLearningOutcome,
                          backref=db.backref('learning_activities', cascade='all, delete-orphan'))

    def __str__(self):
        return self.detail


class EduQALearningActivityAssessment(db.Model):
    __tablename__ = 'eduqa_course_learning_activity_assessments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    detail = db.Column('detail', db.String(), nullable=False)
    learning_activities = db.relationship(EduQALearningActivity,
                                          secondary=learning_activity_assessments, backref=db.backref('assessments'))

    def __str__(self):
        return self.detail


class EduQALearningActivityAssessmentPair(db.Model):
    __tablename__ = 'eduqa_course_learning_activity_assessment_pairs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    learning_activity_id = db.Column(db.ForeignKey('eduqa_course_learning_activities.id'))
    learning_activity_assessment_id = db.Column(db.ForeignKey('eduqa_course_learning_activity_assessments.id'))
    clo_id = db.Column(db.ForeignKey('eduqa_course_learning_outcomes.id'))
    clo = db.relationship(EduQACourseLearningOutcome,
                          backref=db.backref('learning_activity_assessment_pairs', cascade='all, delete-orphan'))
    learning_activity = db.relationship(EduQALearningActivity, backref=db.backref('assessment_pairs',
                                                                                  cascade='all, delete-orphan'))
    learning_activity_assessment = db.relationship(EduQALearningActivityAssessment)
    score_weight = db.Column('weight', db.Numeric(), default=0.0)
    note = db.Column('note', db.Text())

    def __str__(self):
        return self.learning_activity_assessment.detail


class EduQAInstructor(db.Model):
    __tablename__ = 'eduqa_course_instructors'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.ForeignKey('staff_account.id'))
    account = db.relationship(StaffAccount,
                              backref=db.backref('instructor', uselist=False))

    def __init__(self, account_id):
        self.account_id = account_id

    @property
    def fullname(self):
        return self.account.personal_info.fullname


class EduQAInstructorRole(db.Model):
    __tablename__ = 'eduqa_course_instructor_roles'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role = db.Column('role', db.String())
    admin = db.Column('admin', db.Boolean(), default=False)
    credit_hour = db.Column('credit_hour', db.Integer(), default=0)


class EduQACourseSession(db.Model):
    __tablename__ = 'eduqa_course_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.ForeignKey('eduqa_courses.id'))
    start = db.Column(db.DateTime(timezone=True), nullable=False, info={'label': u'เริ่ม'})
    end = db.Column(db.DateTime(timezone=True), nullable=False, info={'label': u'สิ้นสุด'})
    type_ = db.Column(db.String(255), info={'label': u'รูปแบบการสอน',
                                            'choices': [(c, c) for c in
                                                        (u'บรรยาย', u'ปฏิบัติการ', u'กิจกรรม', u'สอบ')]})
    desc = db.Column(db.Text())

    course = db.relationship(EduQACourse, backref=db.backref('sessions', lazy='dynamic'))
    instructors = db.relationship('EduQAInstructor',
                                  secondary=session_instructors,
                                  backref=db.backref('sessions', lazy='dynamic'))
    format = db.Column('format', db.String(),
                       info={'label': u'รูปแบบ', 'choices': [(c, c) for c in [u'ออนไซต์', u'ออนไลน์']]})

    @property
    def total_hours(self):
        delta = self.end - self.start
        return u'{} ชม. {} นาที'.format(delta.seconds // 3600, (delta.seconds // 60) % 60)

    @property
    def total_seconds(self):
        delta = self.end - self.start
        return delta.seconds

    @property
    def topics(self):
        topics = []
        for detail in self.details:
            topics += [topic for topic in detail.topics]
        return topics

    def to_event(self):
        return {
            'title': self.course.en_code if self.course else 'N/A',
            'start': self.start.astimezone(bangkok).isoformat(),
            'end': self.end.astimezone(bangkok).isoformat(),
            'id': self.id,
            'course_id': self.course.id,
            'name': self.course.th_name
        }


class EduQACourseAssignmentSession(db.Model):
    __tablename__ = 'eduqa_course_assignment_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.ForeignKey('eduqa_courses.id'))
    start = db.Column(db.DateTime(timezone=True), nullable=False, info={'label': 'เริ่ม'})
    end = db.Column(db.DateTime(timezone=True), nullable=False, info={'label': 'สิ้นสุด'})
    type_ = db.Column(db.String(255), info={'label': 'รูปแบบกิจกรรม',
                                            'choices': [(c, c) for c in
                                                        ('กรณีศึกษา', 'แบบทดสอบ', 'ทำรายงาน', 'ค้นหาข้อมูล')]})
    title = db.Column('title', db.String(), nullable=False, info={'label': 'หัวข้อ/ชื่อกิจกรรม'})
    desc = db.Column(db.Text(), info={'label': 'รายละเอียด'})

    course = db.relationship(EduQACourse, backref=db.backref('assignments', lazy='dynamic'))
    instructors = db.relationship('EduQAInstructor',
                                  secondary=session_assignment_instructors,
                                  backref=db.backref('assignments', lazy='dynamic'))
    format = db.Column('format', db.String(), info={'label': 'รูปแบบ',
                                                    'choices': [(c, c) for c in ['งานเดี่ยว', 'งานกลุ่ม']]})
    workhours = db.Column('workhours', db.Integer(), default=1, info={'label': 'จำนวนชั่วโมงในการทำกิจกรรม/คน'})

    @property
    def topics(self):
        topics = []
        for detail in self.details:
            topics += [topic for topic in detail.topics]
        return topics

    def to_event(self):
        return {
            'title': self.course.en_code if self.course else 'N/A',
            'start': self.start.astimezone(bangkok).isoformat(),
            'end': self.end.astimezone(bangkok).isoformat(),
            'id': self.id,
            'course_id': self.course.id,
            'name': self.title,
            'type': self.type_,
            'hours': self.workhours,
            'format': self.format
        }


class EduQACourseSessionTopic(db.Model):
    __tablename__ = 'eduqa_course_session_topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column('session_id', db.ForeignKey('eduqa_course_sessions.id'))
    session = db.relationship(EduQACourseSession, backref=db.backref('topics',
                                                                     cascade='all, delete-orphan'))
    topic = db.Column('topic', db.String(), nullable=False, info={'label': u'หัวข้อ'})
    method = db.Column('method', db.String(),
                       info={'label': u'รูปแบบการจัดการสอน',
                             'choices': [(c, c) for c in
                                         [u'บรรยาย', u'ปฏิบัติ', u'อภิปราย', u'กิจกรรมกลุ่ม', u'สาธิต']]})


class EduQACourseSessionDetail(db.Model):
    __tablename__ = 'eduqa_course_session_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.ForeignKey('eduqa_course_sessions.id'))
    staff_id = db.Column(db.ForeignKey('staff_account.id'))
    session = db.relationship(EduQACourseSession,
                              backref=db.backref('details',
                                                 cascade='all, delete-orphan',
                                                 lazy='dynamic'))
    factor = db.Column('factor', db.Integer(), default=1, info={'label': u'ตัวคูณ'})


class EduQACourseSessionDetailRole(db.Model):
    __tablename__ = 'eduqa_course_session_detail_roles'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_detail_id = db.Column(db.ForeignKey('eduqa_course_session_details.id'))
    detail = db.Column('detail', db.Text(), info={'label': u'รายละเอียด'})
    session_detail = db.relationship(EduQACourseSessionDetail,
                                     backref=db.backref('roles', cascade='all, delete-orphan'))
    role_item_id = db.Column('role_item_id', db.ForeignKey('eduqa_course_session_detail_role_items.id'))
    role_item = db.relationship('EduQACourseSessionDetailRoleItem')


class EduQACourseSessionDetailRoleItem(db.Model):
    __tablename__ = 'eduqa_course_session_detail_role_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role = db.Column('role', db.String(), info={'label': u'บทบาท'})
    format = db.Column('format', db.String(), info={'label': u'รูปแบบการสอน'})


class EduQAGradingScheme(db.Model):
    __tablename__ = 'eduqa_grading_schemes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(), nullable=False, info={'label': 'ชื่อ'})

    def __str__(self):
        return self.name


class EduQAGradingSchemeItem(db.Model):
    __tablename__ = 'eduqa_grading_scheme_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order = db.Column('order', db.Integer)
    symbol = db.Column(db.String(), nullable=False, info={'label': 'สัญลักษณ์'})
    detail = db.Column(db.String(), info={'label': 'รายละเอียด'})
    scheme_id = db.Column(db.ForeignKey('eduqa_grading_schemes.id'))
    scheme = db.relationship(EduQAGradingScheme, backref=db.backref('items', order_by='EduQAGradingSchemeItem.order'))
    color_flag = db.Column(db.String())

    def __str__(self):
        return self.symbol


class EduQAGradingSchemeItemCriteria(db.Model):
    __tablename__ = 'eduqa_grading_scheme_item_criteria'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.ForeignKey('eduqa_courses.id'))
    scheme_item_id = db.Column(db.ForeignKey('eduqa_grading_scheme_items.id'))
    scheme_item = db.relationship(EduQAGradingSchemeItem,
                                  backref=db.backref('criteria', lazy='dynamic'))
    criteria = db.Column(db.Text(), info={'label': 'เกณฑ์ (ระบุช่วงคะแนน)'})


class EduQAInstructorEvaluation(db.Model):
    __tablename__ = 'eduqa_instructor_evaluations'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.ForeignKey('eduqa_courses.id'))
    instructor_id = db.Column(db.ForeignKey('eduqa_course_instructors.id'))
    instructor = db.relationship(EduQAInstructor,
                                 backref=db.backref('evaluations', lazy='dynamic'))
    course = db.relationship(EduQACourse, backref=db.backref('evaluations', lazy='dynamic'))
    suggestion = db.Column(db.Text())
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())


class EduQAInstructorEvaluationCategory(db.Model):
    __tablename__ = 'eduqa_instructor_evaluation_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(), nullable=False)

    def __str__(self):
        return self.category


class EduQAInstructorEvaluationItem(db.Model):
    __tablename__ = 'eduqa_instructor_evaluation_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.Integer())
    question = db.Column(db.Text(), nullable=False)
    note = db.Column(db.Text())
    category_id = db.Column(db.ForeignKey('eduqa_instructor_evaluation_categories.id'))
    category = db.relationship(EduQAInstructorEvaluationCategory,
                               backref=db.backref('items', order_by='EduQAInstructorEvaluationItem.number'))


class EduQAInstructorEvaluationChoice(db.Model):
    __tablename__ = 'eduqa_instructor_evaluation_choices'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score = db.Column(db.Numeric())
    label = db.Column(db.String())

    def __str__(self):
        return self.label or self.score


class EduQAInstructorEvaluationResult(db.Model):
    __tablename__ = 'eduqa_instructor_evaluation_results'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    evaluation_id = db.Column(db.ForeignKey('eduqa_instructor_evaluations.id'))
    choice_id = db.Column(db.ForeignKey('eduqa_instructor_evaluation_choices.id'))
    evaluation_item_id = db.Column(db.ForeignKey('eduqa_instructor_evaluation_items.id'))

    choice = db.relationship(EduQAInstructorEvaluationChoice)
    evaluation = db.relationship(EduQAInstructorEvaluation, backref=db.backref('results', lazy='dynamic'))
    item = db.relationship(EduQAInstructorEvaluationItem, backref=db.backref('results'))

    def __str__(self):
        return self.choice
