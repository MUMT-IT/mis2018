from app.main import db
from wtforms_alchemy import model_form_factory, QuerySelectField
from wtforms.validators import Required
from wtforms.widgets import Select
from flask_wtf import FlaskForm
from .models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    """this class is required for wtform_alchemy model to work with FlaskForm model"""
    @classmethod
    def get_session(self):
        return db.session


class ServiceSiteForm(ModelForm):
    class Meta:
        model = HealthServiceSite


class ServiceForm(ModelForm):
    class Meta:
        model = HealthServiceService


class ServiceSlotForm(ModelForm):
    class Meta:
        model = HealthServiceTimeSlot
    service = QuerySelectField(label='Service',
                            validators=[Required()], widget=Select,
                            query_factory=lambda: HealthServiceService.query.all(),
                            get_label=lambda x: x.name,
                            blank_text='Please specify the service')
    site = QuerySelectField(label='Site',
                            validators=[Required()], widget=Select,
                            query_factory=lambda: HealthServiceSite.query.all(),
                            get_label=lambda x: x.name,
                            blank_text='Please specify the site')
