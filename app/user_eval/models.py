from app.main import db


class EvaluationRecord(db.Model):
    __tablename__ = 'user_eval_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_id = db.Column(db.ForeignKey('staff_account.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True))
    score = db.Column(db.Integer(), nullable=False)
    blueprint = db.Column(db.String(), nullable=False)
    comment = db.Column(db.Text(), info={'label': 'Comment'})