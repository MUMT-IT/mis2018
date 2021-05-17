from app.main import db


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
    date = db.Column(db.Date())
    submitted_at = db.Column(db.DateTime(timezone=True))