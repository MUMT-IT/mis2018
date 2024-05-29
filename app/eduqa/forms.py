# -*- coding:utf-8 -*-
from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import SelectMultipleField, widgets, FieldList, FormField, HiddenField, Field, SelectField, \
    DecimalField, TextAreaField, BooleanField, StringField
from wtforms.validators import Optional, InputRequired
from wtforms.widgets import TextInput
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField, ModelFormField, \
    ModelFieldList
from app.eduqa.models import *
from app.room_scheduler.models import RoomResource, RoomEvent, EventCategory
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


class DateTimePickerField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return self.data.strftime('%d-%m-%Y %H:%M:%S')
        else:
            return ''

    def process_formdata(self, value):
        if value[0]:
            self.data = datetime.strptime(value[0], '%d-%m-%Y %H:%M:%S')
        else:
            self.data = None


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

    curriculum = QuerySelectField(u'หลักสูตร', query_factory=lambda: EduQACurriculum.query.all())


class EduCourseCategoryForm(ModelForm):
    class Meta:
        model = EduQACourseCategory


class EduCourseForm(ModelForm):
    class Meta:
        model = EduQACourse

    category = QuerySelectField(u'หมวด',
                                get_label='category',
                                query_factory=lambda: EduQACourseCategory.query.all())
    revision = QuerySelectField(u'หลักสูตร',
                                query_factory=lambda: EduQACurriculumnRevision.query.all())


class EduCourseSessionTopicForm(ModelForm):
    class Meta:
        model = EduQACourseSessionTopic


def is_datetime_valid(start, end):
    return False if start >= end else True


class RoomEventForm(ModelForm):
    class Meta:
        model = RoomEvent
        field_args = {
            'start': {'validators': [Optional()]},
            'end': {'validators': [Optional()]},
            'title': {'validators': [Optional()]}
        }

    room = QuerySelectField('ห้อง', query_factory=lambda: RoomResource.query.all(),
                            allow_blank=True, blank_text='กรุณาเลือกห้อง')
    category = QuerySelectField('Category',
                                query_factory=lambda: EventCategory.query.all(),
                                allow_blank=True)


def create_instructors_form(course):
    class EduCourseSessionForm(ModelForm):
        class Meta:
            model = EduQACourseSession

        instructors = QuerySelectMultipleField('ผู้สอน',
                                               get_label='fullname',
                                               query_factory=lambda: course.instructors,
                                               widget=widgets.ListWidget(prefix_label=False),
                                               option_widget=widgets.CheckboxInput())
        start = DateTimePickerField('เริ่มต้น')
        end = DateTimePickerField('สิ้นสุด')
        topics = FieldList(FormField(EduCourseSessionTopicForm,
                                     default=EduQACourseSessionTopic), min_entries=1)
        events = FieldList(FormField(RoomEventForm, default=RoomEvent), min_entries=0)
        clos = QuerySelectMultipleField('CLO(s)',
                                        query_factory=lambda: course.outcomes,
                                        widget=widgets.ListWidget(prefix_label=False),
                                        option_widget=widgets.CheckboxInput())

    return EduCourseSessionForm


def create_assignment_instructors_form(course):
    class EduCourseAssignmentSessionForm(ModelForm):
        class Meta:
            model = EduQACourseAssignmentSession

        start = DateTimePickerField('เริ่มต้น')
        end = DateTimePickerField('สิ้นสุด')

        instructors = QuerySelectMultipleField(u'ผู้รับผิดชอบ',
                                               get_label='fullname',
                                               query_factory=lambda: course.instructors,
                                               widget=widgets.ListWidget(prefix_label=False),
                                               option_widget=widgets.CheckboxInput())

    return EduCourseAssignmentSessionForm


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


class EduCourseLearningActivityForm(ModelForm):
    learning_activity = QuerySelectField('Learning Activity',
                                         query_factory=lambda: EduQALearningActivity.query.all(),
                                         allow_blank=False, blank_text='Please select')
    assessments = SelectField('Assessments',
                              widget=widgets.ListWidget(prefix_label=False),
                              option_widget=widgets.RadioInput(),
                              coerce=int,
                              validate_choice=False)
    note = TextAreaField('Note')
    score_weight = DecimalField('Weight', validators=[InputRequired()])


class EduCourseLearningActivityAssessmentReportForm(ModelForm):
    class Meta:
        model = EduQALearningActivityAssessmentPair
        only = ['has_problem', 'problem_detail']


class EduCourseLearningOutcomeForm(ModelForm):
    class Meta:
        model = EduQACourseLearningOutcome
        field_args = {'number': {'validators': [InputRequired()]}}

    learning_activity_assessment_forms = FieldList(FormField(EduCourseLearningActivityForm,
                                                             default=EduQALearningActivity), min_entries=0)


class EduGradingSchemeForm(ModelForm):
    grading_scheme = QuerySelectField('Scheme',
                                      query_factory=lambda: EduQAGradingScheme.query.all(),
                                      widget=widgets.ListWidget(prefix_label=False),
                                      option_widget=widgets.RadioInput(),
                                      get_label='name')


class EduFormativeAssessmentForm(ModelForm):
    class Meta:
        model = EduQAFormativeAssessment


class EduQACourseRequiredMaterialsForm(ModelForm):
    class Meta:
        model = EduQACourseRequiredMaterials


class EduQACourseSuggestedMaterialsForm(ModelForm):
    class Meta:
        model = EduQACourseSuggestedMaterials


class EduQACourseResourcesForm(ModelForm):
    class Meta:
        model = EduQACourseResources


def create_clo_plo_form(revision_id):
    class EduQACLOAndPLOForm(ModelForm):
        class Meta:
            model = EduQACourseLearningOutcome

        plos = QuerySelectMultipleField('PLOs',
                                        query_factory=lambda: EduQAPLO.query.filter_by(revision_id=revision_id),
                                        allow_blank=True,
                                        widget=widgets.ListWidget(prefix_label=False),
                                        option_widget=widgets.CheckboxInput())

    return EduQACLOAndPLOForm


class StudentUploadForm(FlaskForm):
    upload_file = FileField('Excel File', validators=[FileRequired()])
    academic_year = StringField('Academic Year', validators=[InputRequired()])
    semester = SelectField('Semester', choices=[(c, c) for c in ('1', '2', '3')],
                           validators=[InputRequired()])
    create_class = BooleanField('Create class if not exists', default=True)
    student_year = SelectField('ชั้น', choices=[(c, c) for c in ('ปี 1', 'ปี 2', 'ปี 3', 'ปี 4')])


class StudentGradeReportUploadForm(FlaskForm):
    upload_file = FileField('Excel File', validators=[FileRequired()])


class StudentGradeEditForm(FlaskForm):
    grade = SelectField('Grade')


class EduCourseSessionReportForm(ModelForm):
    class Meta:
        model = EduQACourseSession
        field_args = {
            'start': {'validators': [Optional()]},
            'end': {'validators': [Optional()]},
        }
        # datetime_format = '%d-%m-%Y %H:%M:%S'

    topics = FieldList(FormField(EduCourseSessionTopicForm,
                                 default=EduQACourseSessionTopic), min_entries=1)
