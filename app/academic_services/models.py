from app.main import db
from werkzeug.security import generate_password_hash, check_password_hash


class ServiceCustomerAccount(db.Model):
    __tablename__ = 'service_customer_accounts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    email = db.Column('email', db.String(), unique=True ,info={'label': 'อีเมล'})
    __password_hash = db.Column('password', db.String(255), nullable=True)
    customer_info_id = db.Column('customer_info_id', db.ForeignKey('service_customer_infos.id'))
    customer_info = db.relationship("ServiceCustomerInfo", backref=db.backref("account", cascade='all, delete-orphan'))

    def __str__(self):
        return self.email

    def is_active(self):
        return True

    def is_authenticated(self):
        return True

    @property
    def password(self):
        raise AttributeError('Password attribute is not accessible.')

    def verify_password(self, password):
        return check_password_hash(self.__password_hash, password)

    @password.setter
    def password(self, password):
        self.__password_hash  = generate_password_hash(password)


class ServiceCustomerInfo(db.Model):
    __tablename__ = 'service_customer_infos'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    title = db.Column('title', db.String(), nullable=False, info={'label': 'คำนำหน้า'})
    firstname = db.Column('firstname', db.String(), nullable=False ,info={'label': 'ชื่อ'})
    lastname = db.Column('lastname', db.String(), nullable=False ,info={'label': 'นามสกุล'})
    organization_name = db.Column('organization_name', db.String() ,info={'label': 'บริษัท'})
    address = db.Column('address', db.Text() ,info={'label': 'ที่อยู่'})
    telephone = db.Column('telephone', db.String() ,info={'label': 'เบอร์โทรศัพท์'})

    def __str__(self):
        return self.fullname

    @property
    def fullname(self):
        if self.organization_name:
            return '{} {} {} ({})'.format(self.title, self.firstname, self.lastname, self.organization_name)
        else:
            return '{} {} {}'.format(self.title, self.firstname, self.lastname)