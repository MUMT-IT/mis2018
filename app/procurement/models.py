# -*- coding:utf-8 -*-
from app.main import db


class ProcurementDetail(db.Model):
    __tablename__ = 'procurement_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    number = db.Column(db.Integer(), nullable=False)