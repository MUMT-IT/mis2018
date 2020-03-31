from app.main import db


class ZoomAccount(db.Model):
    __tablename__ = 'smartclass_scheduler_zoom_accounts'
    id = db.Column('id', db.Integer, primary_key=True, autoincrement=True)
    name = db.Column('name', db.String(), nullable=False)