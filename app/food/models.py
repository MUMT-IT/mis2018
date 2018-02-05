from ..main import db
from sqlalchemy.sql import func
from datetime import datetime

person_and_farm = db.Table('food_person_and_farm',
                           db.Column('person_id', db.Integer(), db.ForeignKey('food_persons.id')),
                           db.Column('farm_id', db.Integer(), db.ForeignKey('food_farms.id'))
                           )

produce_and_farm = db.Table('food_produce_and_farm',
                            db.Column('farm_id', db.Integer(), db.ForeignKey('food_farms.id')),
                            db.Column('produce_id', db.Integer(), db.ForeignKey('food_grown_produces.id'))
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
    sample_lots = db.relationship('SampleLot', backref=db.backref('farm'))
    produce = db.relationship('GrownProduce', secondary=produce_and_farm,
                              backref=db.backref('farms'))

    def ref_id(self):
        return u'{:04}-{:02}-{:02}-{:02}'.format(self.id, self.province_id,
                                                 self.district_id, self.subdistrict_id)


class AgriType(db.Model):
    __tablename__ = 'food_agritype'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    desc = db.Column(db.String(), nullable=True)


class SampleLot(db.Model):
    __tablename__ = 'food_sample_lots'
    id = db.Column(db.Integer(), primary_key=True)
    collected_at = db.Column('collected_at', db.DateTime())
    registered_at = db.Column('registered_at',
                              db.DateTime(), default=datetime.utcnow)
    farm_id = db.Column('farm_id',
                        db.Integer(), db.ForeignKey('food_farms.id'))
    samples = db.relationship('Sample', backref=db.backref('lot'))


class Sample(db.Model):
    __tablename__ = 'food_samples'
    id = db.Column(db.Integer(), primary_key=True)
    lot_id = db.Column('lot_id',
                       db.Integer(), db.ForeignKey('food_sample_lots.id'))
    produce_id = db.Column('produce_id',
                           db.Integer(), db.ForeignKey('food_produces.id'))


class Produce(db.Model):
    __tablename__ = 'food_produces'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(), nullable=False)
    breeds = db.relationship('ProduceBreed', backref=db.backref('produce'))
    grown_produces = db.relationship('GrownProduce',
                                     backref=db.backref('produce'))


class ProduceBreed(db.Model):
    __tablename__ = 'food_produce_breeds'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(), nullable=False)
    produce_id = db.Column('produce_id', db.ForeignKey('food_produces.id'))
    grown_produces = db.relationship('GrownProduce',
                                     backref=db.backref('breed'))


class GrownProduce(db.Model):
    __tablename__ = 'food_grown_produces'
    id = db.Column(db.Integer(), primary_key=True)
    produce_id = db.Column(db.Integer(), db.ForeignKey('food_produces.id'))
    breed_id = db.Column(db.Integer(), db.ForeignKey('food_produce_breeds.id'))
    estimated_area = db.Column(db.Integer(), nullable=True)
