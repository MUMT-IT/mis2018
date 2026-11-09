"""Share one evidence record across independent evaluator submissions."""
from sqlalchemy.exc import IntegrityError

from app.main import db
from .models import EduQAStudentSkillEvidence


def get_or_create_student_evidence(evidence, student, created_by):
    record = EduQAStudentSkillEvidence.query.filter_by(
        evidence_id=evidence.id, student_id=student.id).first()
    if record is not None:
        return record
    try:
        # A competing insert rolls back only this savepoint, not other results.
        with db.session.begin_nested():
            record = EduQAStudentSkillEvidence(
                evidence_id=evidence.id, student_id=student.id,
                created_by_id=created_by.id)
            db.session.add(record)
            db.session.flush()
        return record
    except IntegrityError:
        record = EduQAStudentSkillEvidence.query.filter_by(
            evidence_id=evidence.id, student_id=student.id).first()
        if record is None:
            raise
        return record
