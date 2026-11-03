"""Isolated HTTP checks: no production database or live LINE calls."""
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask
from flask_login import LoginManager, UserMixin
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from app.line_mini_app import bp
from app.line_mini_app.services import LineIdentityError, verify_id_token, verify_access_token, validate_checkin_location


class Staff(UserMixin):
    id = 7
    fullname = 'Test Staff'
    personal_info = SimpleNamespace(org=SimpleNamespace(is_external=False))


class MiniAppTests(unittest.TestCase):
    def setUp(self):
        main = ModuleType('app.main')
        self.home_checkin = Mock(return_value=None)
        main.get_home_checkin_status = self.home_checkin
        main.get_home_calendar_records = Mock(return_value=([], []))
        self.today_calendar = Mock(return_value={'today_label': 'วันนี้', 'items': [], 'count': 0})
        main.build_home_today_calendar = self.today_calendar
        main_patch = patch.dict(sys.modules, {'app.main': main})
        main_patch.start()
        self.addCleanup(main_patch.stop)
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / 'app/templates'))
        self.app.config.update(SECRET_KEY='test-only', TESTING=True,
                               LINE_MINI_APP_CHANNEL_ID='123', LINE_MINI_APP_LIFF_ID='123-test')
        login = LoginManager(self.app)
        login.user_loader(lambda user_id: Staff())
        CSRFProtect(self.app)
        self.app.register_blueprint(bp)
        for endpoint in ('staff.send_time_report_quota', 'home_week_events_summary', 'index', 'auth.account', 'staff.geo_checkin', 'staff.show_leave_info',
                         'staff.index', 'room.index', 'docs_query.index', 'staff.employee_search'):
            self.app.add_url_rule('/test/' + endpoint, endpoint, lambda: '')
        self.app.add_url_rule('/test/csrf', 'test_csrf', lambda: generate_csrf())
        self.client = self.app.test_client()
        self.token = self.client.get('/test/csrf').get_data(as_text=True)

    def post(self, **kwargs):
        return self.client.post('/miniapp/auth', json={'id_token': 'test-token'},
                                headers={'X-CSRFToken': self.token}, **kwargs)

    def test_public_landing_hides_staff_menu(self):
        response = self.client.get('/miniapp/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('class="service"', response.get_data(as_text=True))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_csrf_required(self):
        self.assertEqual(self.client.post('/miniapp/auth', json={'id_token': 'x'}).status_code, 400)

    def test_rejected_identity_cannot_login(self):
        with patch('app.line_mini_app.views.verify_id_token', side_effect=LineIdentityError()):
            self.assertEqual(self.post().status_code, 401)
        with self.client.session_transaction() as session:
            self.assertNotIn('_user_id', session)

    def test_linked_staff_login_and_menu(self):
        models = ModuleType('app.staff.models')
        models.StaffAccount = SimpleNamespace(query=Mock())
        models.StaffAccount.query.filter_by.return_value.first.return_value = Staff()
        with patch.dict(sys.modules, {'app.staff.models': models}), patch(
                'app.line_mini_app.views.verify_id_token', return_value='Uverified'):
            self.assertEqual(self.post().status_code, 200)
        models.StaffAccount.query.filter_by.assert_called_once_with(line_id='Uverified')
        self.assertIn('class="service"', self.client.get('/miniapp/').get_data(as_text=True))

    def test_unlinked_and_external_staff_denied(self):
        models = ModuleType('app.staff.models')
        models.StaffAccount = SimpleNamespace(query=Mock())
        with patch.dict(sys.modules, {'app.staff.models': models}), patch(
                'app.line_mini_app.views.verify_id_token', return_value='Uverified'):
            models.StaffAccount.query.filter_by.return_value.first.return_value = None
            response = self.post()
            self.assertEqual(response.status_code, 403)
            self.assertIn('link_url', response.json)
            user = Staff()
            user.personal_info = SimpleNamespace(org=SimpleNamespace(is_external=True))
            models.StaffAccount.query.filter_by.return_value.first.return_value = user
            self.assertEqual(self.post().status_code, 403)

    def test_landing_shows_existing_home_checkin_time(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '7'
        self.home_checkin.return_value = {
            'checked_in': True, 'time_label': '08:15', 'date_label': '3 พฤศจิกายน 2569',
        }
        response = self.client.get('/miniapp/')
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('08:15 น.', body)
        self.assertIn('วันนี้ลงชื่อเข้างานแล้ว', body)
        self.assertNotIn('วันนี้ยังไม่ได้ลงชื่อเข้างาน', body)
        self.home_checkin.assert_called_once()
        user, now = self.home_checkin.call_args.args
        self.assertIsNotNone(user)
        self.assertIsNotNone(now.tzinfo)

    def test_landing_shows_checkin_action_when_not_checked_in(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '7'
        self.home_checkin.return_value = {'checked_in': False, 'date_label': '3 พฤศจิกายน 2569'}
        body = self.client.get('/miniapp/').get_data(as_text=True)
        self.assertIn('วันนี้ยังไม่ได้ลงชื่อเข้างาน', body)
        self.assertNotIn('วันนี้ลงชื่อเข้างานแล้ว', body)

    def test_landing_includes_homepage_activities_for_staff(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '7'
        self.today_calendar.return_value = {
            'today_label': 'วันนี้ 3 พฤศจิกายน 2569', 'count': 1,
            'items': [{'time': '09:00 - 10:00', 'title': 'ประชุมหน่วยงาน',
                       'meta': 'ห้อง A', 'type': 'room'}],
        }
        body = self.client.get('/miniapp/').get_data(as_text=True)
        self.assertIn('สรุปกิจกรรมสัปดาห์นี้ที่ท่านต้องเข้าร่วม', body)
        self.assertIn('กิจกรรมวันนี้', body)
        self.assertIn('ประชุมหน่วยงาน', body)
        self.assertIn('09:00 - 10:00', body)
        self.assertIn('ห้อง A', body)
        self.assertIn('data-url="/test/home_week_events_summary"', body)
        self.today_calendar.assert_called_once()

    def test_public_landing_does_not_load_personal_activities(self):
        body = self.client.get('/miniapp/').get_data(as_text=True)
        self.assertNotIn('id="week-summary"', body)
        self.assertNotIn('id="today-heading"', body)
        self.today_calendar.assert_not_called()

    def test_checkin_page_lists_all_locations_initially_disabled(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '7'
        response = self.client.get('/miniapp/attendance/checkin')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertEqual(body.count('class="location"'), 4)
        self.assertEqual(body.count(' disabled>'), 4)
        self.assertIn('0.50 กม.', body)
        self.assertIn('ศาลายา', body)
        self.assertIn('ศูนย์การแพทย์กาญจนาภิเษก', body)
        self.assertNotIn('<select', body)

    def test_checkin_location_rejects_invalid_and_outside_coordinates(self):
        validate_checkin_location({'place': 'salaya', 'lat': 13.798807859072065, 'lon': 100.32312238370811})
        for data in (None, {}, {'place': 'unknown'},
                     {'place': 'salaya', 'lat': 0, 'lon': 0},
                     {'place': 'salaya', 'lat': 'nan', 'lon': 100},
                     {'place': 'salaya', 'lat': True, 'lon': 100}):
            with self.assertRaises(ValueError):
                validate_checkin_location(data)

    def test_checkin_reuses_mis_handler_only_after_location_validation(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '7'
        views = ModuleType('app.staff.views')
        views.geo_checkin = Mock(return_value={'message': 'success'})
        with patch.dict(sys.modules, {'app.staff.views': views}):
            invalid = self.client.post('/miniapp/attendance/checkin',
                json={'data': {'place': 'salaya', 'lat': 0, 'lon': 0}},
                headers={'X-CSRFToken': self.token})
            self.assertEqual(invalid.status_code, 400)
            views.geo_checkin.assert_not_called()
            valid = self.client.post('/miniapp/attendance/checkin',
                json={'data': {'place': 'salaya', 'lat': 13.798807859072065,
                               'lon': 100.32312238370811, 'confirm_checkout': False}},
                headers={'X-CSRFToken': self.token})
            self.assertEqual(valid.status_code, 200)
            views.geo_checkin.assert_called_once()

    def test_checkin_requires_csrf_and_staff_session(self):
        self.assertEqual(self.client.post('/miniapp/attendance/checkin', json={}).status_code, 400)
        self.assertEqual(self.client.post('/miniapp/attendance/checkin', json={},
            headers={'X-CSRFToken': self.token}).status_code, 401)

    def test_request_history_requires_login(self):
        response = self.client.get('/miniapp/attendance/requests')
        self.assertEqual(response.status_code, 401)

    def test_request_history_is_scoped_to_staff_and_displays_bangkok_time(self):
        from datetime import datetime, timezone
        with self.client.session_transaction() as session:
            session['_user_id'] = '7'
            session['_fresh'] = True
        model = Mock()
        model.query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(work_datetime=datetime(2026, 11, 3, 1, 30, tzinfo=timezone.utc),
                            is_checkin=True, reason='<script>unsafe</script>',
                            approved_at=None, cancelled_at=None),
            SimpleNamespace(work_datetime=None, is_checkin=False, reason='Closed reason',
                            approved_at=None, cancelled_at=True),
        ]
        models = ModuleType('app.staff.models')
        models.StaffRequestWorkLogin = model
        with patch.dict(sys.modules, {'app.staff.models': models}):
            response = self.client.get('/miniapp/attendance/requests')
        self.assertEqual(response.status_code, 200)
        model.query.filter_by.assert_called_once_with(staff_account_id=7)
        model.query.filter_by.return_value.order_by.return_value.limit.assert_called_once_with(20)
        body = response.get_data(as_text=True)
        self.assertIn('data-quota-url="/test/staff.send_time_report_quota"', body)
        self.assertIn('สรุปโควตาการลงเวลา', body)
        self.assertIn('08:30', body)
        self.assertIn('รออนุมัติ', body)
        self.assertIn('ปิดคำขอ', body)
        self.assertNotIn('<script>unsafe</script>', body)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_request_history_empty_state(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '7'
        model = Mock()
        model.query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        models = ModuleType('app.staff.models')
        models.StaffRequestWorkLogin = model
        with patch.dict(sys.modules, {'app.staff.models': models}):
            response = self.client.get('/miniapp/attendance/requests')
        self.assertIn('ยังไม่มีคำขอรับรองเวลา', response.get_data(as_text=True))

    def test_access_token_fallback_verifies_channel_before_profile(self):
        verification = Mock(status_code=200)
        verification.json.return_value = {'client_id': '123', 'expires_in': 600, 'scope': 'profile'}
        profile = Mock(status_code=200)
        profile.json.return_value = {'userId': 'Uverified'}
        with patch('app.line_mini_app.services.requests.get', side_effect=[verification, profile]) as get:
            self.assertEqual(verify_access_token('access-token', '123'), 'Uverified')
            self.assertEqual(get.call_count, 2)
        for claims in (
            {'client_id': 'other', 'expires_in': 600, 'scope': 'profile'},
            {'client_id': '123', 'expires_in': 0, 'scope': 'profile'},
            {'client_id': '123', 'expires_in': 600, 'scope': 'openid'},
        ):
            verification.json.return_value = claims
            with patch('app.line_mini_app.services.requests.get', return_value=verification) as get:
                with self.assertRaises(LineIdentityError):
                    verify_access_token('access-token', '123')
                self.assertEqual(get.call_count, 1)

    def test_access_token_fallback_logs_in_linked_staff(self):
        models = ModuleType('app.staff.models')
        models.StaffAccount = SimpleNamespace(query=Mock())
        models.StaffAccount.query.filter_by.return_value.first.return_value = Staff()
        with patch.dict(sys.modules, {'app.staff.models': models}), patch(
                'app.line_mini_app.views.verify_access_token', return_value='Uverified') as verify:
            response = self.client.post('/miniapp/auth', json={'access_token': 'access-token'},
                                        headers={'X-CSRFToken': self.token})
            self.assertEqual(response.status_code, 200)
            verify.assert_called_once_with('access-token', '123')

    def test_line_verification_uses_expected_channel(self):
        response = Mock(status_code=200)
        response.json.return_value = {'sub': 'Uverified'}
        with patch('app.line_mini_app.services.requests.post', return_value=response) as post:
            self.assertEqual(verify_id_token('signed-token', '123'), 'Uverified')
            self.assertEqual(post.call_args.kwargs['data']['client_id'], '123')
            response.status_code = 400
            with self.assertRaises(LineIdentityError):
                verify_id_token('wrong-channel-token', '123')


if __name__ == '__main__':
    unittest.main()
