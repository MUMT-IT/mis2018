from main import db

class User(db.Model):
    id = db.Column('id', db.Integer(), primary_key=True)
    email = db.Column('email', db.String(), nullable=False)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column('id', db.String(), primary_key=True)
    refno = db.Column('refno', db.Integer(), nullable=False)
    title = db.Column('title', db.String())
    th_first_name = db.Column('th_first_name', db.String(), nullable=False)
    th_last_name = db.Column('th_last_name', db.String(), nullable=False)
    en_first_name = db.Column('en_first_name', db.String())
    en_last_name = db.Column('en_last_name', db.String())
    class_check_ins = db.relationship('StudentCheckInRecord',
                        backref=db.backref('student'))


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column('id', db.Integer(), primary_key=True)
    refno = db.Column('refno', db.String(), nullable=False)
    th_class_name = db.Column('th_class_name', db.String(), nullable=False)
    en_class_name = db.Column('en_class_name', db.String(), nullable=False)
    academic_year = db.Column('academic_year', db.String(4), nullable=False)
    deadlines = db.relationship('ClassCheckIn', backref=db.backref('class'))


class ClassCheckIn(db.Model):
    __tablename__ = 'class_check_in'
    id = db.Column('id', db.Integer(), primary_key=True)
    class_id = db.Column('class_id', db.ForeignKey('classes.id'))
    deadline = db.Column('deadline', db.String())
    late_mins = db.Column('late_mins', db.Integer())


class StudentCheckInRecord(db.Model):
    __tablename__ = 'student_check_in_records'
    id = db.Column('id', db.Integer(), primary_key=True)
    stud_id = db.Column('stud_id', db.ForeignKey('students.id'))
    classchk_id = db.Column('classchk_id', db.Integer(),
                    db.ForeignKey('class_check_in.id'), nullable=False)
    check_in_time = db.Column('checkin', db.DateTime(), nullable=False)
    check_in_status = db.Column('status', db.String())
    elapsed_mins = db.Column('elapsed_mins', db.Integer())