# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in People models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db.models import Count
from django.utils.translation import ugettext as _

from people.models import Consultant
from crm.models import Subsidiary

def getScopes(subsidiary, team, target="all"):
    """Define scopes than can be used to filter data. Either team, subsidiary or everybody (default). Format is (type, filter, label) where type is "team_id" or "subsidiary_id".
    @:param target: all (default), subsidiary or team
    @:return: scopes, scope_current_filter, scope_current_url_filter"""

    # Gather scopes
    scopes = [(None, "all", _(u"Everybody")), ]
    if target in ("all", "subsidiary"):
        for s in Subsidiary.objects.filter(consultant__active=True, consultant__subcontractor=False,
                                           consultant__productive=True).annotate(num=Count('consultant')).filter(num__gt=0):
            scopes.append(("subsidiary_id", "subsidiary_id=%s" % s.id, str(s)))

    if target in ("all", "team"):
        for manager_id, manager_name in Consultant.objects.filter(active=True, productive=True,
                                                                  subcontractor=False).values_list("staffing_manager",
                                                                                                   "staffing_manager__name").order_by().distinct():
            scopes.append(
                ("team_id", "team_id=%s" % manager_id, _(u"team %(manager_name)s") % {"manager_name": manager_name}))
    # Compute uri and filters
    if subsidiary:
        scope_current_filter = "subsidiary_id=%s" % subsidiary.id
        scope_current_url_filter = "subsidiary/%s" % subsidiary.id
    elif team:
        scope_current_filter = "team_id=%s" % team.id
        scope_current_url_filter = "team/%s" % team.id
    else:
        scope_current_filter = ""
        scope_current_url_filter = ""

    return scopes, scope_current_filter, scope_current_url_filter
