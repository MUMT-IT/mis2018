from ..main import db
from sqlalchemy.sql import func
from ..staff.models import StaffAccount

class ChemItem(db.Model):
    __tablename__ = 'chemdb_items'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(255))
    desc = db.Column('desc', db.String(255))
    msds = db.Column('msds', db.String(255))
    cas = db.Column('cas', db.String(255))
    company_code = db.Column('company_code', db.String(255))
    vendor = db.Column('vendor', db.String(255))
    container_size = db.Column('container_size', db.Numeric())
    container_unit = db.Column('container_unit', db.String(8))
    quantity = db.Column('quantity', db.Integer())
    unit_price = db.Column('unit_price', db.Numeric())
    expire_date = db.Column('expire_date', db.Date())
    created_at = db.Column('created_at', db.Date(), server_default=func.now())
    updated_at = db.Column('updated_at', db.DateTime(timezone=True), onupdate=func.now())
    is_new = db.Column('is_new', db.Boolean())
    location = db.Column('location', db.String(255))
    contact_id = db.Column('contact_id', db.ForeignKey('staff_account.id'))
    contact = db.relationship(StaffAccount, backref=db.backref('chem_items'))
