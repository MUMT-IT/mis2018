# -*- coding:utf-8 -*-
from app.main import db
from app.staff.models import StaffAccount

course_instructors = db.Table('eduqa_course_instructor_assoc',
                              db.Column('course_id', db.Integer, db.ForeignKey('eduqa_courses.id')),
                              db.Column('instructor_id', db.Integer, db.ForeignKey('eduqa_course_instructors.id'))
                              )

session_instructors = db.Table('eduqa_session_instructor_assoc',
                               db.Column('session_id', db.Integer, db.ForeignKey('eduqa_course_sessions.id')),
                               db.Column('instructor_id', db.Integer, db.ForeignKey('eduqa_course_instructors.id'))
                               )


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


class EduQACurriculumnRevision(db.Model):
    __tablename__ = 'eduqa_curriculum_revisions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    curriculum_id = db.Column(db.ForeignKey('eduqa_curriculums.id'))
    curriculum = db.relationship(EduQACurriculum, backref=db.backref('revisions'))
    revision_year = db.Column(db.Date(), nullable=False, info={'label': u'วันที่ปรับปรุงล่าสุด'})


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
    th_desc = db.Column(db.Text(), info={'label': u'คำอธิบายรายวิชา'})
    en_desc = db.Column(db.Text(), info={'label': u'Description'})
    lecture_credit = db.Column(db.Integer, default=0, info={'label': u'หน่วยกิตบรรยาย'})
    lab_credit = db.Column(db.Integer, default=0, info={'label': u'หน่วยกิตปฏิบัติ'})
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

    @property
    def credits(self):
        return self.lecture_credit + self.lab_credit


class EduQAInstructor(db.Model):
    __tablename__ = 'eduqa_course_instructors'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.ForeignKey('staff_account.id'))
    account = db.relationship(StaffAccount)
    courses = db.relationship('EduQACourse',
                              secondary=course_instructors,
                              backref=db.backref('instructors', lazy='dynamic'))

    @property
    def fullname(self):
        return self.account.personal_info.fullname


class EduQACourseSession(db.Model):
    __tablename__ = 'eduqa_course_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.ForeignKey('eduqa_courses.id'))
    start = db.Column(db.DateTime(timezone=True), nullable=False)
    end = db.Column(db.DateTime(timezone=True), nullable=False)
    type_ = db.Column(db.String(255), info={'label': u'ประเภท',
                                            'choices': [(c, c) for c in (u'บรรยาย', u'ปฏิบัติการ', u'กิจกรรม')]})
    desc = db.Column(db.Text())

    course = db.relationship(EduQACourse, backref=db.backref('sessions', lazy='dynamic'))
    instructors = db.relationship('EduQAInstructor',
                                  secondary=session_instructors,
                                  backref=db.backref('sessions', lazy='dynamic'))

    @property
    def total_hours(self):
        delta = self.end - self.start
        return u'{} ชม. {} นาที'.format(delta.seconds//3600, (delta.seconds//60)%60)
