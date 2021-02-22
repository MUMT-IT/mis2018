from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory
from app.main import db
from models import EduQAProgram


BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ProgramForm(ModelForm):
    class Meta:
        model = EduQAProgram
