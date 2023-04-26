from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory
from app.complaint_tracker.models import *


BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ComplaintRecordForm(ModelForm):
    class Meta:
        model = ComplaintRecord