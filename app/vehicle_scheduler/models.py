from app.main import db, ma
from sqlalchemy.sql import func


class VehicleType(db.Model):
    __tablename__ = 'scheduler_vehicle_types'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    type = db.Column('type', db.String(length=32))
    vehicles = db.relationship('VehicleResource', backref='type')

    def __repr__(self):
        return self.type


class VehicleAvailability(db.Model):
    __tablename__ = 'scheduler_vehicle_avails'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    availability = db.Column('availability', db.String(length=32))
    vehicles = db.relationship('VehicleResource', backref='availability')

    def __repr__(self):
        return self.availability


class VehicleResource(db.Model):
    __tablename__ = 'scheduler_vehicle_resources'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    license = db.Column('license', db.String(8), nullable=False)
    maker = db.Column('maker', db.String(16), nullable=False)
    model = db.Column('model', db.String(16))
    year = db.Column('year', db.String(4))
    occupancy = db.Column('occupancy', db.Integer(), nullable=False)
    desc = db.Column('desc', db.Text())
    business_hour_start = db.Column('business_hour_start', db.Time())
    business_hour_end = db.Column('business_hour_end', db.Time())
    availability_id = db.Column('availability_id',
                                db.ForeignKey('scheduler_vehicle_avails.id'))
    type_id = db.Column('type_id', db.ForeignKey('scheduler_vehicle_types.id'))
    # reservations = db.relationship('RoomEvent', backref='room')
