from types import SimpleNamespace
from pathlib import Path
import sys

import pytest
from werkzeug.exceptions import Forbidden


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import main


def test_participant_session_allows_international_relations_endpoint(monkeypatch):
    with main.app.test_request_context('/international-relations/dashboard'):
        main.session['user_type'] = 'international_relations_participant'
        monkeypatch.setattr(main, 'current_user', SimpleNamespace(is_authenticated=True))
        monkeypatch.setattr(
            main,
            'request',
            SimpleNamespace(endpoint='international_relations.dashboard'),
        )

        assert main.restrict_international_relations_participants() is None


def test_participant_session_blocks_host_endpoint(monkeypatch):
    with main.app.test_request_context('/staff'):
        main.session['user_type'] = 'international_relations_participant'
        monkeypatch.setattr(main, 'current_user', SimpleNamespace(is_authenticated=True))
        monkeypatch.setattr(main, 'request', SimpleNamespace(endpoint='staff.index'))

        with pytest.raises(Forbidden):
            main.restrict_international_relations_participants()


def test_staff_session_is_not_restricted(monkeypatch):
    with main.app.test_request_context('/staff'):
        main.session['user_type'] = 'staff'
        monkeypatch.setattr(main, 'current_user', SimpleNamespace(is_authenticated=True))
        monkeypatch.setattr(main, 'request', SimpleNamespace(endpoint='staff.index'))

        assert main.restrict_international_relations_participants() is None


def test_stale_participant_marker_is_cleared(monkeypatch):
    with main.app.test_request_context('/auth/login'):
        main.session['user_type'] = 'international_relations_participant'
        monkeypatch.setattr(main, 'current_user', SimpleNamespace(is_authenticated=False))
        monkeypatch.setattr(main, 'request', SimpleNamespace(endpoint='auth.login'))

        assert main.restrict_international_relations_participants() is None
        assert 'user_type' not in main.session
