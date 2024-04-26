from app.main import db


class ServiceCustomerAccount(db.Model):
    __tablename__ = 'service_customer_accounts'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    email = db.Column('email', db.String(), unique=True ,info={'label': 'อีเมล'})
    confirm_email = db.Column('confirm_email', db.String(), unique=True, info={'label': 'ยืนยันอีเมล'})
    password = db.Column('password', db.String(255) ,info={'label': 'รหัสผ่าน'})
    confirm_password = db.Column('confirm_password', db.String(255), info={'label': 'ยืนยันรหัสผ่าน'})
    customer_info_id = db.Column('customer_info_id', db.ForeignKey('service_customer_infos.id'))
    customer_info = db.relationship("ServiceCustomerInfo", backref=db.backref("account", cascade='all, delete-orphan'))

    def __str__(self):
        return self.email


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