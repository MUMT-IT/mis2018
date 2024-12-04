from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.academic_services.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ServiceCustomerInfoForm(ModelForm):
    class Meta:
        model = ServiceCustomerInfo

    type = QuerySelectField('ประเภท', query_factory=lambda: ServiceCustomerType.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกประเภท', get_label='type')


class ServiceCustomerAddressForm(ModelForm):
    class Meta:
        model = ServiceCustomerAddress