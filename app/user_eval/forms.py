from flask_wtf import FlaskForm
from wtforms.fields.core import RadioField
from wtforms_alchemy import model_form_factory

from app.main import db
from app.user_eval.models import EvaluationRecord

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class EvaluationRecordForm(ModelForm):
    class Meta:
        model = EvaluationRecord
        exclude = ['created_at', 'blueprint']

    score = RadioField('Score', choices=[('5', 'พอใจมาก'),
                                         ('4', 'พอใจ'),
                                         ('3', 'ปานกลาง'),
                                         ('2', 'พอใจน้อย'),
                                         ('1', 'พอใจน้อยมาก')],
                       default='5',
                       coerce=int)

