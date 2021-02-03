from app.main import db
from wtforms_alchemy import model_form_factory, QuerySelectField
from wtforms.widgets import ListWidget, CheckboxInput
from flask_wtf import FlaskForm
from .models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    """this class is required for wtform_alchemy model to work with FlaskForm model"""
    @classmethod
    def get_session(self):
        return db.session


class KMTopicForm(ModelForm):
    class Meta:
        model = KMTopic
