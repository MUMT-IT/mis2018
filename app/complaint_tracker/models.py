from app.main import db
from app.staff.models import StaffAccount


class ComplaintCategory(db.Model):
    __tablename__ = 'complaint_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column('category', db.String(255), nullable=False)

    def __str__(self):
        return u'{}'.format(self.category)


class ComplaintTopic(db.Model):
    __tablename__ = 'complaint_topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(255), nullable=False)

    def __str__(self):
        return u'{}'.format(self.topic)


class ComplaintAdmin(db.Model):
    __tablename__ = 'complaint_admins'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    staff_account = db.Column('staff_account', db.ForeignKey('staff_account.id'))
    is_supervisor = db.Column('is_supervisor', db.Boolean(), default=False)
    topic_id = db.Column('topic_id', db.ForeignKey('complaint_topics.id'))
    topic = db.relationship(ComplaintTopic, backref=db.backref('admins', cascade='all, delete-orphan'))
    admin = db.relationship(StaffAccount)

    def __str__(self):
        return u'{}'.format(self.admin.fullname)
