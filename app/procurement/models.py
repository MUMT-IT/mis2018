# -*- coding:utf-8 -*-
from app.main import db


class ProcurementDetail(db.Model):
    __tablename__ = 'procurement_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    list = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(length=10))
    available = db.Column(db.String(255), nullable=False)