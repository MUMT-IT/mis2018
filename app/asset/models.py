from ..main import db, ma

class AssetItem(db.Model):
    __tablename__ = 'asset_items'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    en_name = db.Column('en_desc', db.String(255), nullable=False)
    th_name = db.Column('th_desc', db.String(255), nullable=False)
    location = db.Column('location', db.String(255))
    value = db.Column('cost', db.Numeric())
    purchased_at = db.Column('purchased_at', db.Date())
    retired_at = db.Column('retired_at', db.Date())
    group_id = db.Column('group_id', db.String(2), nullable=False)
    class_id = db.Column('class_id', db.String(2), nullable=False)
    type_id = db.Column('type_id', db.String(3), nullable=False)
    desc_id = db.Column('desc_id', db.String(4), nullable=False)
    room_id = db.Column('room_id', db.ForeignKey('scheduler_room_resources.id'))
    reservable = db.Column('reservable', db.Boolean, default=False)

    def __str__(self):
        return u'{} {}-{}-{}'.format(self.th_name, self.group_id, self.class_id, self.type_id)
