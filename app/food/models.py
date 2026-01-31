from ..main import db
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
    latitude = db.Column(db.Float(asdecimal=True), nullable=True)
    longitude = db.Column(db.Float(asdecimal=True), nullable=True)
    well_id = db.Column('well_type_id', db.Integer(), db.ForeignKey('well_types.id'))
    well_size_id = db.Column('well_size_id', db.Integer(), db.ForeignKey('well_sizes.id'))
    buffer_id = db.Column('buffer_id', db.Integer(), db.ForeignKey('buffers.id'))
    buffer_detail_id = db.Column('buffer_detail_id', db.Integer(), db.ForeignKey('buffer_details.id'))
    pesticide_use_id = db.Column('pesticide_use_id', db.Integer(), db.ForeignKey('pesticide_uses.id'))
    farm_to_market_id = db.Column('market_id', db.Integer(), db.ForeignKey('farm_to_markets.id'))
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
    # This should be one-to-many relationship instead of many-to-many
    produce = db.relationship('GrownProduce', secondary=produce_and_farm,
                              backref=db.backref('farms'))

    def ref_id(self):
        return u'{:04}-{:02}-{:02}-{:02}'.format(self.id, self.province_id,
                                                 self.district_id, self.subdistrict_id)

    def get_owners(self):
        all_owners = [u'{} {}'.format(owner.firstname, owner.lastname)
                      for owner in self.owners]
        return all_owners


class AgriType(db.Model):
    __tablename__ = 'food_agritype'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    desc = db.Column(db.String(), nullable=True)


class WellType(db.Model):
    __tablename__ = 'well_types'
    id = db.Column(db.Integer(), primary_key=True)
    desc = db.Column(db.String(80), nullable=False)
    farms = db.relationship('Farm', backref='well_type')


class WellSize(db.Model):
    __tablename__ = 'well_sizes'
    id = db.Column(db.Integer(), primary_key=True)
    desc = db.Column(db.String(80), nullable=False)
    farms = db.relationship('Farm', backref='well_size')


class Buffer(db.Model):
    __tablename__ = 'buffers'
    id = db.Column(db.Integer(), primary_key=True)
    desc = db.Column(db.String(80), nullable=False)
    farms = db.relationship('Farm', backref='buffer')


class BufferDetail(db.Model):
    __tablename__ = 'buffer_details'
    id = db.Column(db.Integer(), primary_key=True)
    desc = db.Column(db.String(80), nullable=False)
    farms = db.relationship('Farm', backref='buffer_detail')


class PesticideUse(db.Model):
    __tablename__ = 'pesticide_uses'
    id = db.Column(db.Integer(), primary_key=True)
    desc = db.Column(db.String(80), nullable=False)
    last_use = db.Column(db.Date(), nullable=True)
    farms = db.relationship('Farm', backref='pesticide_use')


class FarmToMarket(db.Model):
    __tablename__ = 'farm_to_markets'
    id = db.Column(db.Integer(), primary_key=True)
    market_type_id = db.Column('market_id', db.Integer(), db.ForeignKey('market_types.id'))
    market_detail_id = db.Column('market_detail_id', db.Integer(), db.ForeignKey('market_details.id'))
    market_detail = db.relationship('MarketDetail', backref='farm_to_market', uselist=False)
    farms = db.relationship('Farm', backref='farm_to_market')


class MarketType(db.Model):
    __tablename__ = 'market_types'
    id = db.Column(db.Integer(), primary_key=True)
    desc = db.Column(db.String(80), nullable=False)
    farm_to_markets = db.relationship('FarmToMarket', backref='market_type')


class MarketDetail(db.Model):
    __tablename__ = 'market_details'
    id = db.Column(db.Integer(), primary_key=True)
    detail = db.Column(db.String(80), nullable=False)


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
    produce_id = db.Column('grown_produce_id',
                           db.Integer(), db.ForeignKey('food_grown_produces.id'))
    pesticide_results = db.relationship('PesticideResult', backref=db.backref('sample'))
    toxico_results = db.relationship('ToxicoResult', backref=db.backref('sample'))
    bact_results = db.relationship('BactResult', backref=db.backref('sample'))
    parasite_results = db.relationship('ParasiteResult', backref=db.backref('sample'))


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
    samples = db.relationship('Sample', backref=db.backref('produce'))


class PesticideTest(db.Model):
    __tablename__ = 'food_pesticide_tests'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(), nullable=False)
    unit = db.Column(db.String())
    cutoff = db.Column(db.Float())
    results = db.relationship('PesticideResult', backref=db.backref('test'))


class PesticideResult(db.Model):
    __tablename__ = 'food_pesticide_results'
    id = db.Column(db.Integer(), primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('food_pesticide_tests.id'))
    sample_id = db.Column(db.Integer, db.ForeignKey('food_samples.id'))
    value = db.Column(db.Float())
    cutoff_value = db.Column(db.Float(), default=0.0)


class ToxicoTest(db.Model):
    __tablename__ = 'food_toxico_tests'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(), nullable=False)
    unit = db.Column(db.String())
    cutoff = db.Column(db.Float())
    results = db.relationship('ToxicoResult', backref=db.backref('test'))


class ParasiteTest(db.Model):
    __tablename__ = 'food_parasite_tests'
    id = db.Column(db.Integer(), primary_key=True)
    organism = db.Column(db.String(), nullable=False)
    stage = db.Column(db.String())
    results = db.relationship('ParasiteResult', backref=db.backref('test'))


class ParasiteResult(db.Model):
    __tablename__ = 'food_parasite_results'
    id = db.Column(db.Integer(), primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('food_parasite_tests.id'))
    sample_id = db.Column(db.Integer, db.ForeignKey('food_samples.id'))
    count = db.Column(db.Integer())
    comment = db.Column(db.String(80))


class ToxicoResult(db.Model):
    __tablename__ = 'food_toxico_results'
    id = db.Column(db.Integer(), primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('food_toxico_tests.id'))
    sample_id = db.Column(db.Integer, db.ForeignKey('food_samples.id'))
    value = db.Column(db.Float())


class BactTest(db.Model):
    __tablename__ = 'food_bact_tests'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(), nullable=False)
    method = db.Column(db.String(), nullable=False)
    unit = db.Column(db.String())
    results = db.relationship('BactResult', backref=db.backref('test'))


class BactResult(db.Model):
    __tablename__ = 'food_bact_results'
    id = db.Column(db.Integer(), primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('food_bact_tests.id'))
    sample_id = db.Column(db.Integer, db.ForeignKey('food_samples.id'))
    value = db.Column(db.String())


class HealthPerson(db.Model):
    __tablename__ = 'food_health_person'
    id = db.Column(db.Integer(), primary_key=True)
    cmscode = db.Column(db.String(), nullable=False)
    firstname = db.Column(db.String())
    lastname = db.Column(db.String())
    pid = db.Column(db.String(13))
    sex = db.Column(db.String())
    age = db.Column(db.Integer())
    mobile = db.Column(db.String())
    title = db.Column(db.String())
    lab_results = db.relationship('HealthServices', backref=db.backref('person'))


class HealthPhyexam(db.Model):
    __tablename__ = 'food_health_phyexam'
    id = db.Column(db.Integer(), primary_key=True)
    cmscode = db.Column(db.String(), nullable=False)
    serviceno = db.Column(db.String(), nullable=False)
    servicedate = db.Column(db.DateTime())
    weight = db.Column(db.Numeric())
    height = db.Column(db.Numeric())
    heartrate = db.Column(db.Integer())
    systolic = db.Column(db.Integer())
    diastolic = db.Column(db.Integer())


class HealthServices(db.Model):
    __tablename__ = 'food_health_services'
    id = db.Column(db.Integer(), primary_key=True)
    cmscode = db.Column(db.String(), nullable=False)
    serviceno = db.Column(db.String(), nullable=False)
    servicedate = db.Column(db.DateTime())
    phyexam_id = db.Column(db.Integer, db.ForeignKey('food_health_phyexam.id'))
    phyexam = db.relationship("HealthPhyexam", backref=db.backref("service", uselist=False))
    labexam_id = db.Column(db.Integer, db.ForeignKey('food_health_lab_results.id'))
    labexam = db.relationship("HealthLabResult", backref=db.backref("service", uselist=False))
    health_person_id = db.Column(db.Integer, db.ForeignKey('food_health_person.id'))


class HealthTest(db.Model):
    __tablename__ = 'food_health_lab_tests'
    id = db.Column(db.Integer(), primary_key=True)
    tcode = db.Column(db.String(), nullable=False)
    name = db.Column(db.String())
    unit = db.Column(db.String())


class HealthLabResult(db.Model):
    __tablename__ = 'food_health_lab_results'
    id = db.Column(db.Integer(), primary_key=True)
    serviceno = db.Column(db.String(), nullable=False)
    data = db.Column(db.JSON)

class SurveyResult(db.Model):
    __tablename__ = 'food_survey_results'
    id = db.Column(db.Integer(), primary_key=True)
    pid = db.Column(db.String(13))
    firstname = db.Column(db.String())
    lastname = db.Column(db.String())
    questions = db.Column(db.JSON)
    results = db.Column(db.JSON)
    survey_datetime = db.Column(db.DateTime())
