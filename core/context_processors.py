# -*- coding: UTF-8 -*-
"""
Pydici core context processors
@author: Aurélien Gâteau (mail@agateau.com)
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.core.cache import cache

from core.utils import user_has_feature
from crm.models import Subsidiary
from crm.utils import get_subsidiary_from_session


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


def scope(request):
    """Returns scope information context"""
    s = cache.get("ACTIVE_SUBSIDIARIES")
    if not s:
        s = Subsidiary.objects.filter(mission__nature="PROD").distinct()
        cache.set("ACTIVE_SUBSIDIARIES", s, 3600*24)
    current_subsidiary = get_subsidiary_from_session(request)
    if current_subsidiary:
        scope_current_filter = "subsidiary_id=%s" % current_subsidiary.id
    else:
        scope_current_filter = ""
    return {"subsidiaries": s,
            "current_subsidiary": current_subsidiary,
            "scope_current_filter": scope_current_filter}
