def raw_score(value):
    """Return a numeric score, or None when the submitted value is not numeric."""
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def weighted_score(value, config):
    """Multiply a raw score by the field's configured weight."""
    config = config or {}
    if not config.get('scorable'):
        return None

    raw = raw_score(value)
    weight = raw_score(config.get('weight'))
    if raw is None or weight is None:
        return None
    return raw * weight


def score_is_in_range(value, config):
    config = config or {}
    if not config.get('scorable'):
        return True
    raw = raw_score(value)
    maximum = raw_score(config.get('max_score'))
    return raw is not None and maximum is not None and 0 <= raw <= maximum
