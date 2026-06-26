from datetime import datetime

from behave import given, then, when


def _seed_ot_fixtures(context, existing_start, existing_end, new_start, new_end):
    from app.models import Org
    from app.staff.models import StaffAccount, StaffJobPosition, StaffPersonalInfo
    from app.ot.models import (
        OtCompensationRate,
        OtJobRole,
        OtPaymentAnnounce,
        OtRecord,
        OtShift,
        OtTimeSlot,
    )

    creator_org = Org(name='Creator Org', is_external=False)
    target_org = Org(name='Target Org', is_external=False)

    creator_person = StaffPersonalInfo(
        en_firstname='HR',
        en_lastname='User',
        th_firstname='เอชอาร์',
        th_lastname='ผู้ใช้',
        org=creator_org,
        academic_staff=False,
    )
    creator_account = StaffAccount(email='hr.user', personal_info=creator_person)
    creator_account.password = 'Secret123!'

    target_person = StaffPersonalInfo(
        en_firstname='Test',
        en_lastname='Employee',
        th_firstname='ทดสอบ',
        th_lastname='บุคลากร',
        org=target_org,
        academic_staff=False,
    )
    target_account = StaffAccount(email='test.employee', personal_info=target_person)

    job_position = StaffJobPosition(th_title='เจ้าหน้าที่', en_title='Officer')
    target_person.job_position = job_position

    announcement = OtPaymentAnnounce(topic='OT Notice', org=creator_org, staff=creator_account)
    job_role = OtJobRole(role='Operator', announcement=announcement, work_for_org=target_org)

    existing_slot = OtTimeSlot(
        start=existing_start.time(),
        end=existing_end.time(),
        announcement=announcement,
        work_for_org=target_org,
        color='#3366ff',
        note='Existing',
    )
    new_slot = OtTimeSlot(
        start=new_start.time(),
        end=new_end.time(),
        announcement=announcement,
        work_for_org=target_org,
        color='#ff6633',
        note='New',
    )

    existing_comp = OtCompensationRate(
        announcement=announcement,
        work_at_org=target_org,
        work_for_org=target_org,
        ot_job_role=job_role,
        time_slot=existing_slot,
        per_hour=100,
    )
    new_comp = OtCompensationRate(
        announcement=announcement,
        work_at_org=target_org,
        work_for_org=target_org,
        ot_job_role=job_role,
        time_slot=new_slot,
        per_hour=100,
    )

    existing_shift = OtShift(existing_start.date(), existing_slot, creator_account)
    existing_record = OtRecord(
        staff=target_account,
        created_staff=creator_account,
        org=creator_org,
        compensation=existing_comp,
        shift=existing_shift,
    )
    existing_shift.records.append(existing_record)

    context.db.session.add_all([
        creator_org,
        target_org,
        creator_person,
        creator_account,
        target_person,
        target_account,
        job_position,
        announcement,
        job_role,
        existing_slot,
        new_slot,
        existing_comp,
        new_comp,
        existing_shift,
        existing_record,
    ])
    context.db.session.commit()

    context.creator_account = creator_account
    context.target_account = target_account
    context.announcement = announcement
    context.new_slot = new_slot
    context.new_comp = new_comp
    context.existing_record_id = existing_record.id
    context.overlap_start = new_start
    context.overlap_end = new_end


@given('an employee already has an OT shift from "{start}" to "{end}"')
def step_impl(context, start, end):
    existing_start = datetime.strptime(start, '%Y-%m-%d %H:%M')
    existing_end = datetime.strptime(end, '%Y-%m-%d %H:%M')
    new_start = datetime.strptime('2026-03-01 21:00', '%Y-%m-%d %H:%M')
    new_end = datetime.strptime('2026-03-01 23:00', '%Y-%m-%d %H:%M')
    _seed_ot_fixtures(context, existing_start, existing_end, new_start, new_end)


@when('I create another OT shift for the same employee from "{start}" to "{end}"')
def step_impl(context, start, end):
    context.overlap_start = datetime.strptime(start, '%Y-%m-%d %H:%M')
    context.overlap_end = datetime.strptime(end, '%Y-%m-%d %H:%M')

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

    response = context.client.post(
        f'/ot/timeslots/timeslot-{context.new_slot.id}/ot-form-modal?start=01/03/2026',
        data={
            'compensation': str(context.new_comp.id),
            'staff': [str(context.target_account.id)],
        },
        follow_redirects=False,
    )
    context.response = response


@then('the system should reject the new OT shift')
def step_impl(context):
    from app.ot.models import OtRecord

    assert context.response.status_code == 200
    body = context.response.get_data(as_text=True)
    assert 'มีข้อมูลการทำOT ในช่วงเวลานี้แล้ว' in body

    records = OtRecord.query.filter_by(staff_account_id=context.target_account.id).all()
    assert len(records) == 1
    assert records[0].id == context.existing_record_id


@then('the error message should say "{message}"')
def step_impl(context, message):
    body = context.response.get_data(as_text=True)
    assert message in body, body
