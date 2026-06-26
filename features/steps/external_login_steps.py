from behave import given, then, when


def _seed_external_staff(context, email, password):
    from app.models import Org
    from app.staff.models import StaffAccount, StaffPersonalInfo

    org = Org(name='External Organization', is_external=True)
    person = StaffPersonalInfo(
        en_firstname='External',
        en_lastname='Employee',
        th_firstname='เอ็กซ์เทอร์นัล',
        th_lastname='พนักงาน',
        org=org,
        academic_staff=False,
    )
    account = StaffAccount(
        email='external.employee',
        external_email=email.lower(),
        personal_info=person,
    )
    account.password = password
    context.db.session.add_all([org, person, account])
    context.db.session.commit()
    context.external_account_id = account.id
    context.external_email = email.lower()
    context.external_username = 'external.employee'
    context.external_password = password


@given('an external staff account with email "{email}" and password "{password}"')
def step_impl(context, email, password):
    _seed_external_staff(context, email, password)


@when('I submit the external login form')
def step_impl(context):
    response = context.client.post(
        '/auth/login-external',
        data={
            'email': context.external_email,
            'password': context.external_password,
            'remember_me': 'y',
        },
        follow_redirects=True,
    )
    context.response = response
    context.login_value = context.external_email


@when('I submit the external login form with "{username}" as a username')
def step_impl(context, username):
    response = context.client.post(
        '/auth/login-external',
        data={
            'email': username,
            'password': context.external_password,
            'remember_me': 'y',
        },
        follow_redirects=True,
    )
    context.response = response
    context.login_value = username


@then('I should be logged in and directed to the external landing page')
def step_impl(context):
    from app.staff.models import StaffAccount

    assert context.response.status_code == 200
    body = context.response.get_data(as_text=True)
    assert 'External Employee Portal' in body
    assert 'External employee access only' in body

    account = StaffAccount.query.filter_by(external_email=context.external_email).first()
    assert account is not None
    assert account.id == context.external_account_id
