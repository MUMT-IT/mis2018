from app.main import db, ma


class RoomType(db.Model):
    __tablename__ = 'scheduler_room_types'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    type = db.Column('type', db.String(length=32))
    rooms = db.relationship('RoomResource', backref='type')


class RoomAvailability(db.Model):
    __tablename__ = 'scheduler_room_avails'
    id = db.Column('id', db.Integer(), primary_key=True,
                   autoincrement=True)
    availability = db.Column('availability', db.String(length=32))
    rooms = db.relationship('RoomResource', backref='availability')


class RoomResource(db.Model):
    __tablename__ = 'scheduler_room_resources'
    id = db.Column('id', db.Integer(), primary_key=True,
                    autoincrement=True)
    location = db.Column('location', db.String(length=16))
    number = db.Column('number', db.String(16))
    occupancy = db.Column('occupancy', db.Integer(), nullable=False)
    desc = db.Column('desc', db.Text())
    business_hour_start = db.Column('business_hour_start', db.Time())
    business_hour_end = db.Column('business_hour_end', db.Time())
    availability_id = db.Column('availability_id',
                                db.ForeignKey('scheduler_room_avails.id'))
    type_id = db.Column('type_id', db.ForeignKey('scheduler_room_types.id'))
