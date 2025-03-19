from flask_wtf import FlaskForm
from app.software_request.models import *
from wtforms_alchemy import model_form_factory

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session