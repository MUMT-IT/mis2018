# -*- coding:utf-8 -*-
from app.main import db
from app.staff.models import StaffAccount, StaffPersonalInfo


class DocSendOut(db.Model):
    __tablename__ = 'doc_send_out'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    running_no = db.Column('running_no', db.Integer)
    title = db.Column('title', db.String)
    send_to = db.Column('send_to', db.String)
    created_at = db.Column('created_at', db.DateTime(timezone=True))
    org_id = db.Column('org_id', db.Integer(), db.ForeignKey('orgs.id'), nullable=False)
    file_name = db.Column(db.String(255))
    url = db.Column(db.String(255))


class DocOrg(db.Model):
    __tablename__ = 'doc_orgs'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    org_document_code = db.Column('org_document_code', db.Integer())
    detail = db.Column('detail', db.String())


class DocCategory(db.Model):
    __tablename__ = 'doc_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)

    def __str__(self):
        return self.name


class DocRound(db.Model):
    __tablename__ = 'doc_rounds'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date(), info={'label': 'Date'}, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True))
    created_by = db.Column(db.ForeignKey('staff_account.id'))
    creator = db.relationship(StaffAccount)

    def __str__(self):
        return self.date.strftime('%d/%m/%Y')


class DocRoundOrg(db.Model):
    __tablename__ = 'doc_round_orgs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sent_at = db.Column(db.DateTime(timezone=True))
    round_id = db.Column(db.ForeignKey('doc_rounds.id'))
    org_id = db.Column(db.ForeignKey('orgs.id'))
    finished_at = db.Column(db.DateTime(timezone=True))

    org = db.relationship('Org')
    round = db.relationship(DocRound, backref=db.backref('targets',
                                                         lazy='dynamic',
                                                         cascade='all, delete-orphan'))


class DocDocument(db.Model):
    __tablename__ = 'doc_documents'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    round_id = db.Column(db.ForeignKey('doc_rounds.id'))
    round = db.relationship(DocRound, backref=db.backref('documents',
                                                         lazy='dynamic',
                                                         order_by='DocDocument.number',
                                                         cascade='all, delete-orphan'))
    number = db.Column(db.Integer(), info={'label': u'Number'})
    deadline = db.Column(db.DateTime(timezone=True),
                         info={'label': 'Deadline'})
    addedAt = db.Column(db.DateTime(timezone=True))
    file_name = db.Column(db.String(255))
    url = db.Column(db.String(255))
    priority = db.Column(db.String(255),
                         info={'label': 'Priority',
                               'choices': [(c, c) for c in [u'ปกติ', u'ด่วน', u'ด่วนที่สุด']]})
    stage = db.Column(db.String(255),
                         info={'label': 'Stage',
                               'choices': [(c, c) for c in [u'drafting', u'ready', u'sent']]})
    title = db.Column(db.String(255), info={'label': 'Title'})
    summary = db.Column(db.Text(), info={'label': 'Summary'})
    comment = db.Column(db.Text(), info={'label': 'Comment'})
    category_id = db.Column(db.ForeignKey('doc_categories.id'))
    category = db.relationship(DocCategory, backref=db.backref('documents', lazy='dynamic',
                                                               cascade='all, delete-orphan'))

    def get_recipients(self, round_org_id):
        receipt = self.doc_receipts.filter_by(round_org_id=round_org_id, doc_id=self.id).first()
        if receipt:
            return receipt.members
        else:
            return []


receipt_receivers = db.Table('doc_receipt_receivers_assoc',
                               db.Column('receipt_id', db.Integer, db.ForeignKey('doc_receive_records.id')),
                               db.Column('personal_info_id', db.Integer, db.ForeignKey('staff_personal_info.id'))
                               )


class DocReceiveRecord(db.Model):
    __tablename__ = 'doc_receive_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    predefined_comment = db.Column(db.String(255), info={'label': 'Predefined Comment',
                                                         'choices': [(c, c) for c in [u'แจ้งเพื่อทราบ',
                                                                                      u'แจ้งเพื่อพิจารณา',
                                                                                      u'ขอความร่วมมือเข้าร่วม']]})
    comment = db.Column(db.Text, info={'label': 'Additional Comment'})
    sent_at = db.Column(db.DateTime(timezone=True))
    sender_id = db.Column(db.ForeignKey('staff_account.id'))
    round_org_id = db.Column(db.ForeignKey('doc_round_orgs.id'))
    round_org = db.relationship(DocRoundOrg, backref=db.backref('sent_records',
                                                            lazy='dynamic'))
    doc_id = db.Column(db.ForeignKey('doc_documents.id'))
    rejected = db.Column(db.Boolean(), default=False)
    members = db.relationship(StaffPersonalInfo, secondary=receipt_receivers)
    sender = db.relationship(StaffAccount)
    doc = db.relationship(DocDocument, backref=db.backref('doc_receipts',
                                                          lazy='dynamic',
                                                          cascade='all, delete-orphan'))


class DocRoundOrgReach(db.Model):
    __tablename__ = 'doc_round_org_reaches'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reached_at = db.Column(db.DateTime(timezone=True))
    reacher_id = db.Column(db.ForeignKey('staff_account.id'))
    reacher = db.relationship(StaffAccount)
    created_at = db.Column(db.DateTime(timezone=True))

    round_org_id = db.Column(db.ForeignKey('doc_round_orgs.id'))

    round_org = db.relationship(DocRoundOrg, backref=db.backref('round_reaches',
                                                                lazy='dynamic',
                                                                cascade='all, delete-orphan'))


class DocDocumentReach(db.Model):
    __tablename__ = 'doc_document_reaches'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reached_at = db.Column(db.DateTime(timezone=True))
    reacher_id = db.Column(db.ForeignKey('staff_account.id'))
    reacher = db.relationship(StaffAccount, backref=db.backref('doc_reaches', lazy='dynamic'))
    doc_id = db.Column(db.ForeignKey('doc_documents.id'))
    starred = db.Column(db.Boolean(False))
    note = db.Column(db.Text())
    doc = db.relationship(DocDocument, backref=db.backref('reaches',
                                                          lazy='dynamic',
                                                          cascade='all, delete-orphan'))
    round_org_id = db.Column(db.ForeignKey('doc_round_orgs.id'))
    round_org = db.relationship(DocRoundOrg, backref=db.backref('doc_reaches', lazy='dynamic'))
    sender_comment = db.Column(db.Text())
    receiver_comment = db.Column(db.Text())
    receiver_commented_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True))
