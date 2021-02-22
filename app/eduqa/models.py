# -*- coding:utf-8 -*-
from app.main import db


class EduQADegree(db.Model):
    __tablename__ = 'eduqa_degrees'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(), info={'label': u'ระดับ',
                                        'choices': ((c,i) for c,i in
                                                    [(u'ปริญญาตรี', 1),
                                                     (u'ปริญญาโท',2),
                                                     (u'ปริญญาเอก',3)
                                                 ])
                                        })


class EduQAProgram(db.Model):
    __tablename__ = 'eduqa_programs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    degree_id = db.Column(db.ForeignKey('eduqa_degrees.id'))
    degree = db.relationship(EduQADegree, backref=db.backref('programs'))


class EduQACurriculum(db.Model):
    __tablename__ = 'eduqa_curriculums'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    program_id = db.Column(db.ForeignKey('eduqa_programs.id'),
                           )
    program = db.relationship(EduQAProgram, backref=db.backref('curriculums'))