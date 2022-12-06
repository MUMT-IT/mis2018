# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets, FieldList, FormField, IntegerField, HiddenField
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField, ModelFormField, \
    ModelFieldList
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
                                               query_factory=lambda: course.instructors,
                                               widget=widgets.ListWidget(prefix_label=False),
                                               option_widget=widgets.CheckboxInput())
        topics = FieldList(FormField(EduCourseSessionTopicForm,
                                     default=EduQACourseSessionTopic), min_entries=1)

    return EduCourseSessionForm


def CourseSessionDetailRoleFormFactory(format):
    class EduCourseSessionDetailRoleForm(ModelForm):
        class Meta:
            model = EduQACourseSessionDetailRole

        role_item = QuerySelectField(u'บทบาท',
                                     get_label='role',
                                     query_factory=lambda: EduQACourseSessionDetailRoleItem
                                     .query.filter_by(format=format))

    return EduCourseSessionDetailRoleForm


def CourseSessionDetailFormFactory(learning_format):
    class EduCourseSessionDetailForm(ModelForm):
        class Meta:
            model = EduQACourseSessionDetail

        EduCourseSessionDetailRoleForm = CourseSessionDetailRoleFormFactory(learning_format)
        roles = FieldList(FormField(EduCourseSessionDetailRoleForm,
                                    default=EduQACourseSessionDetailRole), min_entries=1)

    return EduCourseSessionDetailForm


class EduCourseInstructorRoleFormField(ModelForm):
    class Meta:
        model = EduQACourseInstructorAssociation

    instructor_id = HiddenField('instructor_id')
    role = QuerySelectField('Role', get_label='role',
                            query_factory=lambda: EduQAInstructorRole.query.all())


class EduCourseInstructorRoleForm(ModelForm):
    roles = ModelFieldList(ModelFormField(EduCourseInstructorRoleFormField), min_entries=0)
