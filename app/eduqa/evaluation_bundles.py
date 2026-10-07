"""Validation shared by combined skill evaluations."""
from app.dynamic_forms.scoring import score_is_in_range


def bundle_answers(sections, form_data):
    """Validate every section before creating any database records."""
    answers = []
    errors = []
    for assignment, evidence in sections:
        section_answers = []
        if not assignment.version.fields:
            errors.append('{}: แบบประเมินยังไม่มีคำถาม'.format(evidence.skill.name))
        for field in assignment.version.fields:
            values = form_data.getlist('assignment_{}_field_{}'.format(assignment.id, field.id))
            value = values[0] if values else None
            label = '{}: {}'.format(evidence.skill.name, field.label)
            if field.required and (not values or all(v == '' for v in values)):
                errors.append('{}: กรุณากรอกข้อมูล'.format(label))
            if value not in (None, '') and not score_is_in_range(value, field.config):
                errors.append('{}: คะแนนไม่อยู่ในช่วงที่กำหนด'.format(label))
            if field.field_type in ('select', 'multiselect'):
                allowed = {option.value for option in field.options}
                if any(v not in allowed for v in values if v != ''):
                    errors.append('{}: คำตอบไม่ถูกต้อง'.format(label))
            if field.field_type == 'boolean' and value not in (None, '', 'true', 'false'):
                errors.append('{}: คำตอบไม่ถูกต้อง'.format(label))
            if field.field_type == 'multiselect':
                value = values
            elif field.field_type == 'boolean':
                value = value == 'true'
            section_answers.append((field, value))
        answers.append((assignment, evidence, section_answers))
    return answers, errors
