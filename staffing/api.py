# coding: utf-8
"""
Pydici staffing API.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import datetime
from django.http import JsonResponse

from core.utils import previousMonth, nextMonth
from core.decorator import pydici_non_public, pydici_feature
from staffing.models import Mission


@pydici_non_public
@pydici_feature("reports")
def mission_list(request, start_date=None, end_date=None):
    """Return json list of missions with timesheet activity on given timeframe"""
    if end_date is None:
        end_date = nextMonth(datetime.date.today())
    else:
        end_date = datetime.date(int(end_date[0:4]), int(end_date[4:6]), 1)
    if start_date is None:
        start_date = previousMonth(previousMonth(datetime.date.today()))
    else:
        start_date = datetime.date(int(start_date[0:4]), int(start_date[4:6]), 1)

    if (end_date - start_date).days > (2*366):
        return JsonResponse({"error": "timeframe cannot exceed 24 month" }, status=400)

    missions = Mission.objects.filter(update_date__gte=start_date, update_date__lte=end_date)
    data = []
    for mission in missions:
        mission_data = {"mission_id": mission.mission_id(),
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
                        "lead_id": None,
                        }
        if mission.lead:
            mission_data.update({"lead_id": mission.lead.deal_id,
                                 "lead_name": mission.lead.name,
                                 "lead_price": mission.lead.sales or 0,
                                 "lead_subsidiary_code": mission.lead.subsidiary.code,
                                 "lead_subsidiary_name": mission.lead.subsidiary.name,
                                 "client_company_name": mission.lead.client.organisation.company.name,
                                 "client_company_code": mission.lead.client.organisation.company.code,
                                 "client_organization_name": mission.lead.client.organisation.name,
                                 })
            if mission.lead.responsible:
                mission_data.update({"lead_responsible_name": mission.lead.responsible.name,
                                     "lead_responsible_trigramme": mission.lead.responsible.trigramme,
                                     })

        data.append(mission_data)
    return JsonResponse(list(data), safe=False)
