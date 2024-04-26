from flask_wtf import FlaskForm
from wtforms import FieldList, FormField
from wtforms_alchemy import model_form_factory
from app.academic_services.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ServiceCustomerAccountForm(ModelForm):
    class Meta:
        model = ServiceCustomerAccount


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    account = FieldList(FormField(ServiceCustomerAccountForm, default=ServiceCustomerAccount), min_entries=1)