# coding: utf-8
"""
Pydici staffing API.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import datetime
from django.http import JsonResponse

from core.utils import previousMonth
from core.decorator import pydici_non_public, pydici_feature
from staffing.models import Mission

@pydici_non_public
@pydici_feature("reports")
def mission_list(request, start_date=None, end_date=None):
    """Return json list of missions with timesheet activity on given timeframe"""
    if end_date is None:
        end_date = previousMonth(datetime.date.today())
    else:
        end_date = datetime.date(int(end_date[0:4]), int(end_date[4:6]), 1)
    if start_date is None:
        start_date = previousMonth(previousMonth(datetime.date.today()))
    else:
        start_date = datetime.date(int(start_date[0:4]), int(start_date[4:6]), 1)

    missions = Mission.objects.filter(timesheet__working_date__gte=start_date, timesheet__working_date__lte=end_date)
    missions = missions.distinct()[:500]  # Limit data to avoid stupid things
    data = []
    for mission in missions:
        data.append({"lead_id": mission.lead.deal_id if mission.lead else None,
                     "description": mission.description,
                     "billing_mode": mission.billing_mode,
                     "nature": mission.nature,
                     "management_mode": mission.management_mode,
                     "subsidiary_code": mission.subsidiary.code,
                     "subsidiary_name": mission.subsidiary.name,
                     "responsible": mission.responsible.trigramme if mission.responsible else None,
                     "price": mission.price,
                     "analytic_code": mission.mission_analytic_code(),
                     "marketing_product_code": mission.marketing_product.code if mission.marketing_product else None,
                     "marketing_product_description": mission.marketing_product.description if mission.marketing_product else None,
                     "archived": not mission.active,
                     "archived_date": mission.archived_date,
                     "start_date": mission.start_date,
                     "end_date": mission.end_date,
                     "mission_id": mission.mission_id()
                     })
    return JsonResponse(list(data), safe=False)
