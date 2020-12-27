# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Crm models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.apps import apps
from django.db.models import Avg, F
from django.core.cache import cache

def get_subsidiary_from_session(request):
    """ Returns current subsidiary or None if not defined or scope is all"""
    Subsidiary = apps.get_model("crm", "Subsidiary")
    current_subsidiary = None
    if "subsidiary_id" in request.session:
        if request.session["subsidiary_id"] > 0:  # 0 mean all subsidiaries
            current_subsidiary = Subsidiary.objects.get(id=request.session["subsidiary_id"])
    return current_subsidiary


def get_clients_rate_ranking(subsidiary=None):
    """compute average daily rate and return ordered list of (client id, average daily rate)"""
    key = "CLIENT_RATE_RANKING"
    if subsidiary:
        key += "_" + subsidiary.code

    res = cache.get(key)
    if res:
        return res

    FinancialCondition = apps.get_model("staffing", "FinancialCondition")
    financialConditions = FinancialCondition.objects.filter(consultant__timesheet__charge__gt=0,  # exclude null charge
                                                            consultant__timesheet=F("mission__timesheet")
                                                            # Join to avoid duplicate entries
                                                            ).select_related()
    if subsidiary:
        financialConditions = financialConditions.filter(mission__lead__subsidiary=subsidiary)

    financialConditions = financialConditions.values("mission__lead__client").order_by("mission__lead__client")
    financialConditions = financialConditions.annotate(Avg("daily_rate")).order_by("-daily_rate__avg")
    financialConditions = financialConditions.values_list("mission__lead__client", "daily_rate__avg")

    cache.set(key, financialConditions, 3600*24)
    return financialConditions