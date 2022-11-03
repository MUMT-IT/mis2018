# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets, FieldList, FormField
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField
from app.main import db
from models import *
from app.staff.models import (StaffAcademicPositionRecord,
                              StaffAcademicPosition,
                              StaffEduDegree)

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ProgramForm(ModelForm):
    class Meta:
        model = EduQAProgram


class AcademicPositionRecordForm(ModelForm):
    class Meta:
        model = StaffAcademicPositionRecord

    position = QuerySelectField(u'ตำแหน่ง',
                                get_label='fullname_th',
                                query_factory=lambda: StaffAcademicPosition.query.all())


class EduDegreeRecordForm(ModelForm):
    class Meta:
        model = StaffEduDegree


class EduProgramForm(ModelForm):
    class Meta:
        model = EduQAProgram


class EduCurriculumnForm(ModelForm):
    class Meta:
        model = EduQACurriculum

    program = QuerySelectField(u'โปรแกรม',
                               get_label='name',
                               query_factory=lambda: EduQAProgram.query.all())


class EduCurriculumnRevisionForm(ModelForm):
    class Meta:
        model = EduQACurriculumnRevision

    curriculum = QuerySelectField(u'หลักสูตร',
                                  get_label='th_name',
                                  query_factory=lambda: EduQACurriculum.query.all()
                                  )


class EduCourseCategoryForm(ModelForm):
    class Meta:
        model = EduQACourseCategory


class EduCourseForm(ModelForm):
    class Meta:
        model = EduQACourse

    category = QuerySelectField(u'หมวด',
                                get_label='category',
                                query_factory=lambda: EduQACourseCategory.query.all())


class EduCourseSessionTopicForm(ModelForm):
    class Meta:
        model = EduQACourseSessionTopic


def create_instructors_form(course):
    class EduCourseSessionForm(ModelForm):
        class Meta:
            model = EduQACourseSession

        instructors = QuerySelectMultipleField(u'ผู้สอน',
                                               get_label='fullname',
                                               query_factory=lambda: course.instructors.all(),
                                               widget=widgets.ListWidget(prefix_label=False),
                                               option_widget=widgets.CheckboxInput())
        topics = FieldList(FormField(EduCourseSessionTopicForm,
                                     default=EduQACourseSessionTopic), min_entries=1)

    return EduCourseSessionForm


class EduCourseSessionDetailRoleForm(ModelForm):
    class Meta:
        model = EduQACourseSessionDetailRole


class EduCourseSessionDetailForm(ModelForm):
    class Meta:
        model = EduQACourseSessionDetail
    roles = FieldList(FormField(EduCourseSessionDetailRoleForm,
                                default=EduQACourseSessionDetailRole), min_entries=1)
