from flask_wtf import FlaskForm
from wtforms import widgets
from wtforms_alchemy import model_form_factory, QuerySelectField
from app.main import db
from .models import PACommittee, PARound, PARequest
from ..models import Org, StaffAccount

BaseModelForm = model_form_factory(FlaskForm)

class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session

class PACommitteeForm(ModelForm):
    class Meta:
        model = PACommittee

    round = QuerySelectField('รอบการประเมิน',
                           allow_blank=False,
                           query_factory=lambda: PARound.query.all())

    org = QuerySelectField('หน่วยงาน',
                                  get_label='name',
                                  allow_blank=False,
                                  query_factory=lambda: Org.query.all())

    staff = QuerySelectField('ผู้ประเมิน',
                           get_label='fullname',
                           allow_blank=False,
                           query_factory=lambda: StaffAccount.query.filter(
                               StaffAccount.personal_info.has(retired=False)).all())


class PARequestForm(ModelForm):
    class Meta:
        model = PARequest