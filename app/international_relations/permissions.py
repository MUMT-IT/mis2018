"""Authorization helpers for International Relations staff screens."""

from functools import wraps

from flask import abort, redirect, request, url_for
from flask_login import current_user
from flask_principal import Permission

from .models import InternalRelationParticipant


international_relations_admin_permission = Permission(
    ('international_relations_admin', None, None),
    ('admin', None, None),
)


def participant_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for(
                'international_relations.login',
                next=request.url,
            ))
        if not isinstance(current_user._get_current_object(), InternalRelationParticipant):
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def international_relations_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not international_relations_admin_permission.can():
            abort(403)
        return view(*args, **kwargs)

    return wrapped
