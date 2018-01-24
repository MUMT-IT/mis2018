from ..main import db
from sqlalchemy.sql import func


person_and_farm = db.Table('food_person_and_farm',
        db.Column('person_id', db.Integer(), db.ForeignKey('food_persons.id')),
        db.Column('farm_id', db.Integer(), db.ForeignKey('food_farms.id'))
    )


class Person(db.Model):
    __tablename__ = 'food_persons'
    id = db.Column(db.Integer(), primary_key=True)
    firstname = db.Column(db.String(200), nullable=False)
    lastname = db.Column(db.String(200), nullable=False)
    farms = db.relationship('Farm',
                    secondary=person_and_farm,
                    backref=db.backref('owners', lazy='dynamic'),
                    lazy='dynamic')


class Farm(db.Model):
    __tablename__ = 'food_farms'
    id = db.Column(db.Integer(), primary_key=True)
    estimated_total_size = db.Column(
            db.Float(asdecimal=True), nullable=True)
    estimated_leased_size = db.Column(
            db.Float(asdecimal=True), nullable=True)
    estimated_owned_size = db.Column(
            db.Float(asdecimal=True), nullable=True)
    agritype = db.Column('agritype', db.Integer(),
            db.ForeignKey('food_agritype.id'))
    province = db.Column('province_id', db.Integer(),
            db.ForeignKey('provinces.id'))
    district = db.Column('district_id', db.Integer(),
            db.ForeignKey('districts.id'))
    subdistrict = db.Column('subdistrict_id', db.Integer(),
            db.ForeignKey('subdistricts.id'))


class AgriType(db.Model):
    __tablename__ = 'food_agritype'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    desc = db.Column(db.String(), nullable=True)
