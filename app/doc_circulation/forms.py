from app.main import db
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms_alchemy import (model_form_factory, QuerySelectField)
from wtforms_components import DateTimeField
from wtforms.widgets import Select
from .models import *


BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class RoundForm(ModelForm):
    class Meta:
        model = DocRound


class DocumentForm(ModelForm):
    class Meta:
        model = DocDocument

    category = QuerySelectField('Category', query_factory=lambda: DocCategory.query.all(),
                                get_label='name', blank_text='Select category..', allow_blank=False)

    upload = FileField('File Upload')
