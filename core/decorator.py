# coding: utf-8
"""
Pydici views decorators
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import resolve_url
from django.utils.decorators import method_decorator


from core.utils import user_has_features


def _setify(value):
    if isinstance(value, str):
        return set((value,))
    else:
        return set(value)


def pydici_non_public(function=None):
    """
    Decorator for views that restrict access to "internal" users. For now
    it relies on the staff user flag and is mostly used to allow external people like
    subcontractors to access only to homepage and timesheet page
    """
    actual_decorator = user_passes_test(lambda u: u.is_staff, login_url=None)
    if function:
        return actual_decorator(function)
    return actual_decorator


class PydiciNonPublicdMixin(object):
    @method_decorator(pydici_non_public)
    def dispatch(self, request, *args, **kwargs):
        return super(PydiciNonPublicdMixin, self).dispatch(request, *args, **kwargs)


def pydici_feature(features, login_url=None):
    """
    Decorator for views which require users to have access to `feature`.

    `features` can be either a string, a tuple of strings or a set of strings.
    If it is a tuple or a set then the user must have access to all features.
    """
    feature_set = _setify(features)
    return user_passes_test(lambda u: user_has_features(u, feature_set), login_url=login_url)


class PydiciFeatureMixin(object):
    """
    Decorator to check feature access for class-based views.

    Usage:

        class MyView(PydiciFeatureMixin, UpdateView):
            pydici_feature = "search"

    or:

        class MyView(PydiciFeatureMixin, UpdateView):
            pydici_feature = { "search", "edit" }
    """
    def dispatch(self, request, *args, **kwargs):
        feature_set = _setify(self.pydici_feature)

        if not user_has_features(request.user, feature_set):
            resolved_login_url = resolve_url(settings.LOGIN_URL)
            path = request.get_full_path()
            return redirect_to_login(path, resolved_login_url, REDIRECT_FIELD_NAME)
        return super(PydiciFeatureMixin, self).dispatch(request, *args, **kwargs)
