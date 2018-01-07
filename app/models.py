from main import db

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column('id', db.String(), primary_key=True)
    refno = db.Column('refno', db.Integer(), nullable=False)
    title = db.Column('title', db.String())
    th_first_name = db.Column('th_first_name', db.String(), nullable=False)
    th_last_name = db.Column('th_last_name', db.String(), nullable=False)
    en_first_name = db.Column('en_first_name', db.String())
    en_last_name = db.Column('en_last_name', db.String())


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column('id', db.Integer(), primary_key=True)
    refno = db.Column('refno', db.String(), nullable=False)
    th_class_name = db.Column('th_class_name', db.String(), nullable=False)
    en_class_name = db.Column('en_class_name', db.String(), nullable=False)
    academic_year = db.Column('academic_year', db.String(4), nullable=False)