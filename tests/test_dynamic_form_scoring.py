import importlib.util
from pathlib import Path


SCORING_PATH = Path(__file__).parents[1] / 'app' / 'dynamic_forms' / 'scoring.py'
SPEC = importlib.util.spec_from_file_location('dynamic_form_scoring', SCORING_PATH)
scoring = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scoring)

raw_score = scoring.raw_score
score_is_in_range = scoring.score_is_in_range
weighted_score = scoring.weighted_score


def test_weighted_score_multiplies_raw_score_by_weight():
    config = {'scorable': True, 'max_score': 5, 'weight': 2}

    assert weighted_score('1', config) == 2
    assert weighted_score('4', config) == 8


def test_non_scorable_field_has_no_weighted_score():
    assert weighted_score('4', {'scorable': False, 'max_score': 5, 'weight': 20}) is None


def test_invalid_raw_scores_are_rejected():
    config = {'scorable': True, 'max_score': 5, 'weight': 20}

    assert score_is_in_range('0', config)
    assert score_is_in_range('5', config)
    assert not score_is_in_range('6', config)
    assert not score_is_in_range('not a number', config)
    assert raw_score(True) is None
