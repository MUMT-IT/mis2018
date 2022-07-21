# from app.main import db
#
#
# class ReceiptDetail(db.Model):
#     __tablename__ = 'receipt_details'
#     id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
#     code = db.Column('code', db.String())
#     copy_number = db.Column('copy_number', db.Integer, default=1)
#     book_number = db.Column('book_number', db.String())
#     created_datetime = db.Column('created_datetime', db.DateTime(timezone=True))
#     address = db.Column('address', db.Text())
#     payment_method = db.Column('payment_method', db.String())
#     paid_amount = db.Column('paid_amount', db.Numeric(), default=0.0)
#     card_number = db.Column('card_number', db.String())