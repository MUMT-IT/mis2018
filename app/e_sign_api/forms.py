from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import PasswordField, BooleanField
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory
from app.main import db

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class CertificateFileForm(FlaskForm):
    file_upload = FileField('PFX file', validators=[DataRequired()])
    image_upload = FileField('Image file')


class TestPdfSignForm(FlaskForm):
    doc = FileField('Test Document', validators=[DataRequired()])
    passphrase = PasswordField('Passphrase', validators=[DataRequired()])