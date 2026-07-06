from behave import given, then, when


def _seed_hr_user(context):
    from app.models import Org
    from app.staff.models import Role, StaffAccount, StaffEmployment, StaffJobPosition, StaffPersonalInfo

    internal_org = Org(name='Internal Org', is_external=False)
    hr_person = StaffPersonalInfo(
        en_firstname='HR',
        en_lastname='User',
        th_firstname='เอชอาร์',
        th_lastname='ผู้ใช้',
        org=internal_org,
        academic_staff=False,
    )
    hr_account = StaffAccount(
        email='hr.user',
        personal_info=hr_person,
    )
    hr_account.password = 'Secret123!'
    hr_role = Role(role_need='hr', action_need=None, resource_id=None)
    hr_account.roles.append(hr_role)

    external_org = Org(name='External Org', is_external=True)
    employment = StaffEmployment(title='Permanent')
    job_position = StaffJobPosition(th_title='เจ้าหน้าที่', en_title='Officer')

    context.db.session.add_all([internal_org, hr_person, hr_account, hr_role, external_org, employment, job_position])
    context.db.session.commit()

    context.hr_account = hr_account
    context.external_org = external_org
    context.employment = employment
    context.job_position = job_position


@given(u'a staff account belongs to external organization')
def step_impl(context):
    _seed_hr_user(context)


@when(u'an HR submit the staff account form')
def step_impl(context):
    login_response = context.client.post(
        '/auth/login',
        data={
            'email': 'hr.user',
            'password': 'Secret123!',
            'remember_me': 'y',
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    form_data = {
        'email': 'external.employee',
        'external_email': 'external.employee@example.com',
        'th_title': 'นางสาว',
        'th_firstname': 'ทดสอบ',
        'th_lastname': 'บุคลากร',
        'en_firstname': 'Test',
        'en_lastname': 'Staff',
        'position': 'Officer',
        'employed_date': '01/01/2024',
        'finger_scan_id': '12345',
        'sap_id': 'SAP001',
        'employment_id': str(context.employment.id),
        'job_id': str(context.job_position.id),
        'org_id': str(context.external_org.id),
    }

    context.response = context.client.post(
        '/staff/for-hr/staff-info/create',
        data=form_data,
        follow_redirects=True,
    )


@then(u"the HR should be directed to the HR's staff edit password page")
def step_impl(context):
    from app.staff.models import StaffAccount

    created_account = StaffAccount.query.filter_by(external_email='external.employee@example.com').first()
    assert created_account is not None
    assert created_account.email == 'external.employee'
    assert created_account.personal_info.org is not None
    assert created_account.personal_info.org.is_external is True
    assert context.response.status_code == 200
    assert context.response.request.path == f'/staff/for-hr/staff-info/search-account/edit-pwd/{created_account.id}'
    body = context.response.get_data(as_text=True)
    assert 'แก้ไขรหัสผ่านของ' in body
    assert 'ตั้งรหัสผ่านใหม่' in body
