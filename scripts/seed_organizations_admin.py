"""Seed script to create OrganizationType and Organization mock data."""
from app.main import app, db
from app.continuing_edu.models import CEOrganizationType, CEOrganization


TYPES_AND_ORGS = {
    ('hospital', 'โรงพยาบาล'): [
        'Mahidol University Hospital',
        'Siriraj Hospital',
        'Ramathibodi Hospital',
    ],
    ('university', 'มหาวิทยาลัย'): [
        'Mahidol University',
        'Chulalongkorn University',
        'Kasetsart University',
    ],
    ('research_institute', 'สถาบันวิจัย'): [
        'National Research Institute',
        'Biomedical Research Center'
    ],
    ('private_clinic', 'คลินิกเอกชน'): [
        'Bangkok Medical Clinic',
        'HealthPlus Clinic'
    ],
    ('company', 'บริษัท'): [
        'BioTech Co., Ltd.',
        'MedSupply International'
    ],
    ('government_agency', 'หน่วยงานภาครัฐ'): [
        'Ministry of Public Health',
        'Department of Medical Services'
    ],
    ('other', 'อื่นๆ'): [
        'Independent Practitioner'
    ],
}


def seed():
    with app.app_context():
        for (code_en, code_th), names in TYPES_AND_ORGS.items():
            ot = CEOrganizationType.query.filter_by(name_en=code_en).first()
            if not ot:
                ot = CEOrganizationType(name_en=code_en, name_th=code_th, is_user_defined=False)
                db.session.add(ot)
                db.session.commit()
            for n in names:
                existing = CEOrganization.query.filter_by(name=n).first()
                if not existing:
                    org = CEOrganization(name=n, organization_type_id=ot.id, is_user_defined=False)
                    db.session.add(org)
        db.session.commit()
        print('Seeding complete')


if __name__ == '__main__':
    seed()
