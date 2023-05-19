# coding: utf-8

"""
Module that handle asynchronous tasks
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from datetime import date

from django.core import management
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.cache import get_cache_key
from django.core.cache import cache
from celery import shared_task

from staffing.views import turnover_pivotable, graph_profile_rates
from leads.views import graph_leads_pipe, leads_pivotable
from people.views import graph_people_count
from crm.views import clients_ranking
from core.utils import get_fiscal_year, create_fake_request
from crm.models import Subsidiary

@shared_task
def sessions_cleanup():
    """Cleanup django sessions"""
    management.call_command("clearsessions", verbosity=0)

@shared_task
def view_warmup():
    """Warmup cache for heavy views"""
    if settings.DEBUG:
        # Don't bother developers with that.
        return
    user = User.objects.filter(is_superuser=True).first()
    subsidiaries_id = list(Subsidiary.objects.filter(mission__nature="PROD").distinct().values_list("id", flat=True))
    subsidiaries_id.append(0) # Add the "all" subsidiaries
    current_fiscal_year = get_fiscal_year(date.today())
    ## Request env is important as it is used to build header cache key
    hosts = [h for h in settings.ALLOWED_HOSTS if h != "localhost"]
    env = {"SERVER_NAME": hosts[0] if hosts else "localhost", "SERVER_PORT": "443", "wsgi.url_scheme": "https"}
    for url_name, view, kwargs, subsidiary_context in (
            ("staffing:turnover_pivotable", turnover_pivotable, {}, True),
            ("staffing:turnover_pivotable_year", turnover_pivotable, { "year": current_fiscal_year }, True),
            ("staffing:turnover_pivotable_year", turnover_pivotable, {"year": current_fiscal_year - 1 }, True),
            ("staffing:turnover_pivotable_all", turnover_pivotable, {"year": "all"}, True),
            ("staffing:graph_profile_rates", graph_profile_rates, {}, True),
            ("leads:graph_leads_pipe", graph_leads_pipe, {}, True),
            ("people:graph_people_count", graph_people_count, {}, True),
            ("crm:clients_ranking", clients_ranking, {}, True),
            ("leads:leads-pivotable", leads_pivotable, {}, True),
            ("leads:leads-pivotable-year", leads_pivotable, { "year": current_fiscal_year }, True),
            ("leads:leads-pivotable-year", leads_pivotable, {"year": current_fiscal_year - 1 }, True),
    ):
        context = [None, ]
        if subsidiary_context:
            context.extend(subsidiaries_id)
        for c in context:
            url = reverse(url_name, kwargs=kwargs)
            if c:
                url += "?subsidiary_id=%s" % c
            request = create_fake_request(user=user, url=url, env=env)
            if c: # inject subsidiary id in session to have proper subsidiary name in selector
                request.session["subsidiary_id"] = c
            key = get_cache_key(request)
            if cache.has_key(key):  # purge cache if it exists
                cache.delete(key)
            view(request, **kwargs)
