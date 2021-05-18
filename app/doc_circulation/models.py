# -*- coding:utf-8 -*-
from app.main import db
from app.staff.models import StaffAccount


class DocCategory(db.Model):
    __tablename__ = 'doc_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)

    def __str__(self):
        return self.name


class DocRound(db.Model):
    __tablename__ = 'doc_rounds'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    status = db.Column(db.String(255),
                       info={'label': 'Status',
                             'choices': ((c, c.title()) for c in ['drafting',
                                                                  'submitted',
                                                                  'approved'])
                             }
                       )
    date = db.Column(db.Date(), info={'label': 'Date'}, nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True))

    def __str__(self):
        return self.date.strftime('%d/%m/%Y')


class DocDocument(db.Model):
    __tablename__ = 'doc_documents'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    round_id = db.Column(db.ForeignKey('doc_rounds.id'))
    deadline = db.Column(db.DateTime(timezone=True),
                         info={'label': 'Deadline'})
    addedAt = db.Column(db.DateTime(timezone=True))
    file_name = db.Column(db.String(255))
    url = db.Column(db.String(255))
    priority = db.Column(db.String(255),
                         info={'label': 'Priority',
                               'choices': [(c, c) for c in [u'ปกติ', u'ด่วน', u'ด่วนที่สุด']]})
    title = db.Column(db.String(255), info={'label': 'Title'})
    summary = db.Column(db.Text(), info={'label': 'Summary'})
    comment = db.Column(db.Text(), info={'label': 'Comment'})
    category_id = db.Column(db.ForeignKey('doc_categories.id'))

    round = db.relationship(DocRound, backref=db.backref('documents', lazy='dynamic',
                                                         cascade='all, delete-orphan'))
    category = db.relationship(DocCategory, backref=db.backref('documents', lazy='dynamic',
                                                               cascade='all, delete-orphan'))


class DocReceiveRecord(db.Model):
    __tablename__ = 'doc_receive_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doc_id = db.Column(db.ForeignKey('doc_documents.id'))
    staff_id = db.Column(db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref='recv_records')
    doc = db.relationship(DocDocument, backref='recv_records')
    viewed_at = db.Column(db.DateTime(timezone=True))
