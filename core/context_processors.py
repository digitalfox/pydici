# -*- coding: UTF-8 -*-
"""
Pydici core context processors
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from collections import defaultdict
from importlib import import_module

from django.conf import settings

from core.utils import user_has_feature


class FeatureWrapper(object):
    def __init__(self, user):
        self.user = user

    def __getitem__(self, feature):
        return user_has_feature(self.user, str(feature))

    def __contains__(self, feature):
        return bool(self[feature])


def feature(request):
    """
    Returns context variables to check if the current user has access to Pydici
    features.
    """
    if hasattr(request, 'user'):
        user = request.user
    else:
        from django.contrib.auth.models import AnonymousUser
        user = AnonymousUser()

    return {
        'pydici_feature': FeatureWrapper(user),
    }
