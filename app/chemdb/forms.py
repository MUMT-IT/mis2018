from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory
from app.main import db
from models import ChemItem

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ChemItemForm(ModelForm):
    class Meta:
        model = ChemItem