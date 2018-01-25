from ..main import db
from sqlalchemy.sql import func
from datetime import datetime


person_and_farm = db.Table('food_person_and_farm',
        db.Column('person_id', db.Integer(), db.ForeignKey('food_persons.id')),
        db.Column('farm_id', db.Integer(), db.ForeignKey('food_farms.id'))
    )


class Person(db.Model):
    __tablename__ = 'food_persons'
    id = db.Column(db.Integer(), primary_key=True)
    firstname = db.Column(db.String(200), nullable=False)
    lastname = db.Column(db.String(200), nullable=False)
    pid = db.Column(db.String(13), nullable=True)
    farms = db.relationship('Farm',
                    secondary=person_and_farm,
                    backref=db.backref('owners', lazy='dynamic'),
                    lazy='dynamic')
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    def __str__(self):
        return u'<{}>: {} {}'.format(self.id, self.firstname, self.lastname)


class Farm(db.Model):
    __tablename__ = 'food_farms'
    id = db.Column(db.Integer(), primary_key=True)
    estimated_total_size = db.Column(
            db.Float(asdecimal=True), nullable=True)
    estimated_leased_size = db.Column(
            db.Float(asdecimal=True), nullable=True)
    estimated_owned_size = db.Column(
            db.Float(asdecimal=True), nullable=True)
    village = db.Column(db.String(), nullable=True)
    street = db.Column(db.String(), nullable=True)
    agritype_id = db.Column('agritype', db.Integer(),
            db.ForeignKey('food_agritype.id'))
    province_id = db.Column('province_id', db.Integer(),
            db.ForeignKey('provinces.id'))
    district_id = db.Column('district_id', db.Integer(),
            db.ForeignKey('districts.id'))
    subdistrict_id = db.Column('subdistrict_id', db.Integer(),
            db.ForeignKey('subdistricts.id'))
    created_at = db.Column(db.DateTime(), default=datetime.utcnow)

    def ref_id(self):
        return u'{:04}-{:02}-{:02}-{:02}'.format(self.id,self.province_id,
                self.district_id, self.subdistrict_id)


class AgriType(db.Model):
    __tablename__ = 'food_agritype'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    desc = db.Column(db.String(), nullable=True)
