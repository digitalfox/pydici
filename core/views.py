# coding: utf-8
"""
Pydici core views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.db.models import Q
from django.contrib.auth.decorators import login_required

from core.decorator import pydici_non_public
from leads.models import Lead
from people.models import Consultant
from crm.models import Company, Contact
from staffing.models import Mission
from billing.models import ClientBill
from people.views import consultant_home
import pydici.settings


@login_required
def index(request):

    request.session["mobile"] = False

    try:
        consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    except Consultant.DoesNotExist:
        consultant = None

    if consultant:
        return consultant_home(request, consultant.id)
    else:
        # User is not a consultant. Go for default index page.
        return render_to_response("core/index.html",
                                  {"user": request.user},
                                   RequestContext(request))


def mobile_index(request):
    """Mobile device index page"""
    # Mark session as "mobile"
    request.session["mobile"] = True
    try:
        consultant = Consultant.objects.get(trigramme__iexact=request.user.username)
    except Consultant.DoesNotExist:
        # Mobile pydici does not exist for non consultant users
        # switch back to classical home page
        request.session["mobile"] = False
        return index(request)
    if consultant.subcontractor:
        # Don't show that to subcontractors
        companies = []
        missions = []
        leads = []
    else:
        companies = Company.objects.filter(clientorganisation__client__lead__mission__timesheet__consultant=consultant).distinct()
        missions = consultant.active_missions().filter(nature="PROD").filter(probability=100)
        leads = Lead.objects.active().order_by("creation_date")
    return render_to_response("core/m.index.html",
                              {"user": request.user,
                               "consultant" : consultant,
                               "companies" : companies,
                               "missions" : missions,
                               "leads" : leads },
                              RequestContext(request))

@pydici_non_public
def search(request):
    """Very simple search function on all major pydici objects"""

    consultants = None
    companies = None
    leads = None
    missions = None
    contacts = None
    bills = None

    words = request.GET.get("q", "")
    words = words.split()

    if words:
        # Consultant
        if request.GET.get("consultant"):
            consultants = Consultant.objects.filter(active=True)
            for word in words:
                consultants = consultants.filter(Q(name__icontains=word) |
                                                 Q(trigramme__icontains=word))
            consultants = consultants.distinct()

        # Companies
        if request.GET.get("company"):
            companies = Company.objects.all()
            for word in words:
                companies = companies.filter(name__icontains=word)
            companies = companies.distinct()

        # Contacts
        if request.GET.get("contact"):
            contacts = Contact.objects.all()
            for word in words:
                contacts = contacts.filter(name__icontains=word)
            contacts = contacts.distinct()

        # Leads
        if request.GET.get("lead"):
            leads = Lead.objects.all()
            for word in words:
                leads = leads.filter(Q(name__icontains=word) |
                                     Q(description__icontains=word) |
                                     Q(tags__name__iexact=word) |
                                     Q(client__contact__name__icontains=word) |
                                     Q(client__organisation__company__name__icontains=word) |
                                     Q(client__organisation__name__iexact=word) |
                                     Q(deal_id__icontains=word[:-1]))  # Squash last letter that could be mission letter
            leads = leads.distinct()

        # Missions
        if request.GET.get("mission"):
            missions = Mission.objects.all()
            for word in words:
                missions = missions.filter(Q(deal_id__icontains=word) |
                                           Q(description__icontains=word))

            # Add missions from lead
            if leads:
                missions = set(missions)
                for lead in leads:
                    for mission in lead.mission_set.all():
                        missions.add(mission)
                missions = list(missions)

        # Bills
        if request.GET.get("bill"):
            bills = ClientBill.objects.all()
            for word in words:
                bills = bills.filter(Q(bill_id__icontains=word) |
                                     Q(comment__icontains=word))

            # Add bills from lead
            if leads:
                bills = set(bills)
                for lead in leads:
                    for bill in lead.clientbill_set.all():
                        bills.add(bill)
            # Sort
            bills = list(bills)
            bills.sort(key=lambda x: x.creation_date)

    return render_to_response("core/search.html",
                              {"query" : " ".join(words),
                               "consultants": consultants,
                               "companies" : companies,
                               "contacts" : contacts,
                               "leads" : leads,
                               "missions" : missions,
                               "bills" : bills,
                               "user": request.user },
                               RequestContext(request))


@pydici_non_public
def dashboard(request):
    """Tactical management dashboard. This views is in core module because it aggregates data
    accross different modules"""

    return render_to_response("core/dashboard.html",
                              {},
                              RequestContext(request))


def internal_error(request):
    """Custom internal error view.
    Like the default builtin one, but with context to allow proper menu display with correct media path"""
    return render_to_response("500.html", {}, RequestContext(request))


def forbiden(request):
    """When access is denied..."""
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        # Ajax request, use stripped forbiden page
        template = "core/_access_forbiden.html"
    else:
        # Standard request, use full forbiden page with menu
        template = "core/forbiden.html"
    return render_to_response(template,
                              {"admins": pydici.settings.ADMINS, },
                              RequestContext(request))
