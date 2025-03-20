from app.main import db


class SoftwareRequestType(db.Model):
    __tablename__ = 'software_request_type'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    type = db.Column('type', db.String(), info={'label': 'ประเภทคำขอ'})