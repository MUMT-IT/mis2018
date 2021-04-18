# -*- coding:utf-8 -*-
from app.main import db

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