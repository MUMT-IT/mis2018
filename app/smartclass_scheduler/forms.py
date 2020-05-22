from app.main import db
from flask_wtf import FlaskForm
from wtforms_alchemy import (model_form_factory, QuerySelectField)
from wtforms_components import DateTimeField
from wtforms.widgets import Select
from .models import *


BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class SmartClassOnlineAccountEventForm(ModelForm):
    class Meta:
        model = SmartClassOnlineAccountEvent