from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, SelectField
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.PA.models import *
from app.main import db

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class PAKPIForm(ModelForm):
    class Meta:
        model = PAKPI


class PAItemForm(ModelForm):
    class Meta:
        model = PAItem

    items = FieldList(FormField(PAKPIForm, default=PAKPI), min_entries=1)
    type = SelectField('ประเภท',
                       choices=[(c, c) for c in ['ปริมาณ', 'คุณภาพ', 'เวลา', 'ความคุ้มค่า', 'ความพึงพอใจ']],
                       validators=[DataRequired()])


class PAKPIItemForm(ModelForm):
    class Meta:
        model = PAKPIItem

    level = QuerySelectField(query_factory=lambda: PALevel.query.all(),
                           get_label='level',
                           label=u'เกณฑ์การประเมิน',
                           blank_text='กรุณาเลือกเกณฑ์การประเมิน..', allow_blank=True)



