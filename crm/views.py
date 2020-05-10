# coding: utf-8
"""
Pydici crm views. Http request are processed here.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import json
from datetime import date, datetime, timedelta

from django.shortcuts import render
from django.db.models import Sum, Min, Count
from django.views.decorators.cache import cache_page
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import DetailView, ListView
from django.contrib import messages
from django.utils.translation import ugettext as _
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import permission_required
from django.utils.safestring import mark_safe
from django.template.loader import get_template


from crm.models import Company, Client, ClientOrganisation, Contact, AdministrativeContact, MissionContact,\
    BusinessBroker, Supplier, Subsidiary
from crm.forms import ClientForm, ClientOrganisationForm, CompanyForm, ContactForm, MissionContactForm,\
    AdministrativeContactForm, BusinessBrokerForm, SupplierForm
from crm.utils import get_subsidiary_from_session
from people.models import Consultant, ConsultantProfile
from leads.models import Lead
from core.decorator import pydici_non_public, pydici_feature, PydiciNonPublicdMixin, PydiciFeatureMixin
from core.utils import COLORS
from billing.models import ClientBill


class ContactReturnToMixin(object):
    """Mixin class to return to contact detail if return_to args is not provided"""
    def get_success_url(self):
        if self.model in (MissionContact, BusinessBroker):
            target = self.object.contact.id
        else:
            target = self.object.id
        return self.request.GET.get('return_to', False) or reverse_lazy("crm:contact_detail", args=[target, ])


class ThirdPartyMixin(PydiciFeatureMixin):
    pydici_feature = "3rdparties"


class FeatureContactsWriteMixin(PydiciFeatureMixin):
    pydici_feature = set(["3rdparties", "contacts_write"])


class ContactCreate(PydiciNonPublicdMixin, ThirdPartyMixin, ContactReturnToMixin, CreateView):
    model = Contact
    template_name = "core/form.html"
    form_class = ContactForm

    def get_initial(self):
        try:
            defaultPointOfContact = Consultant.objects.get(trigramme=self.request.user.username.upper())
            return { 'contact_points': [defaultPointOfContact,]}
        except Consultant.DoesNotExist:
            return {}


class ContactUpdate(PydiciNonPublicdMixin, ThirdPartyMixin, ContactReturnToMixin, UpdateView):
    model = Contact
    template_name = "core/form.html"
    form_class = ContactForm


class ContactDelete(PydiciNonPublicdMixin, FeatureContactsWriteMixin, DeleteView):
    model = Contact
    template_name = "core/delete.html"
    form_class = ContactForm
    success_url = reverse_lazy("crm:contact_list")

    def form_valid(self, form):
        messages.add_message(self.request, messages.INFO, _("Contact removed successfully"))
        return super(ContactDelete, self).form_valid(form)

    @method_decorator(permission_required("crm.delete_contact"))
    def dispatch(self, *args, **kwargs):
        return super(ContactDelete, self).dispatch(*args, **kwargs)


class ContactDetail(PydiciNonPublicdMixin, ThirdPartyMixin, DetailView):
    model = Contact


class ContactList(PydiciNonPublicdMixin, ThirdPartyMixin, ListView):
    model = Contact


@pydici_non_public
@pydici_feature("3rdparties")
def contact_list(request):
    return render(request, "crm/contact_list.html",
                  {"data_url": reverse("crm:all_contacts_table_DT"),
                   "datatable_options": ''' "columnDefs": [{ "orderable": false, "targets": [1] },
                                                   { className: "hidden-xs hidden-sm hidden-md", "targets": [6]}],
                                   "order": [[0, "asc"]] ''',
                   "user": request.user})


class MissionContactCreate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, ContactReturnToMixin, CreateView):
    model = MissionContact
    template_name = "core/form.html"
    form_class = MissionContactForm


class MissionContactUpdate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, ContactReturnToMixin, UpdateView):
    model = MissionContact
    template_name = "core/form.html"
    form_class = MissionContactForm


class BusinessBrokerCreate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, ContactReturnToMixin, CreateView):
    model = BusinessBroker
    template_name = "core/form.html"
    form_class = BusinessBrokerForm


class BusinessBrokerUpdate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, ContactReturnToMixin, UpdateView):
    model = BusinessBroker
    template_name = "core/form.html"
    form_class = BusinessBrokerForm


class SupplierCreate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, ContactReturnToMixin, CreateView):
    model = Supplier
    template_name = "core/form.html"
    form_class = SupplierForm


class SupplierUpdate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, ContactReturnToMixin, UpdateView):
    model = Supplier
    template_name = "core/form.html"
    form_class = SupplierForm


class AdministrativeContactCreate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, CreateView):
    model = AdministrativeContact
    template_name = "core/form.html"
    form_class = AdministrativeContactForm

    def get_initial(self):
        return {'company': self.request.GET.get("company")}

    def get_success_url(self):
        return self.request.GET.get('return_to', False) or reverse_lazy("crm:company_detail", args=[self.object.company.id, ])


class AdministrativeContactUpdate(PydiciNonPublicdMixin, FeatureContactsWriteMixin, UpdateView):
    model = AdministrativeContact
    template_name = "core/form.html"
    form_class = AdministrativeContactForm

    def get_success_url(self):
        return self.request.GET.get('return_to', False) or reverse_lazy("crm:company_detail", args=[self.object.company.id, ])


@pydici_non_public
@pydici_feature("3rdparties")
def client(request, client_id=None):
    """Client creation or modification"""
    client = None
    try:
        if client_id:
            client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        pass

    if request.method == "POST":
        if client:
            form = ClientForm(request.POST, instance=client)
        else:
            form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            client.save()
            return HttpResponseRedirect(reverse("crm:company_detail", args=[client.organisation.company.id]))
    else:
        if client:
            form = ClientForm(instance=client)  # A form that edit current client
        else:
            form = ClientForm()  # An unbound form

    return render(request, "crm/client.html", {"client": client,
                                               "form": form,
                                               "user": request.user})


@pydici_non_public
@pydici_feature("3rdparties")
def client_organisation_company_popup(request):
    """Client, organisation and company creation in one popup"""
    template = get_template("crm/client-popup.html")
    result = {"success": False}
    if request.method == "POST":
        clientForm = ClientForm(request.POST, prefix="client")
        organisationForm = ClientOrganisationForm(request.POST, prefix="organisation")
        companyForm = CompanyForm(request.POST, prefix="company")
        contactForm = ContactForm(request.POST, prefix="contact")

        if contactForm.is_valid():
            contact = contactForm.save()
        else:
            contact = None

        if companyForm.is_valid():
            company = companyForm.save()
        else:
            company = None

        client = None
        if clientForm.is_valid():
            client = clientForm.save(commit=False)
        else:
            # clientForm may be invalid because client organisation is a new one
            if organisationForm.is_valid():
                organisation = organisationForm.save()
                clientForm.data = clientForm.data.copy()
                clientForm.data["client-organisation"] = organisation.id  # Inject organisation in client form
                clientForm.full_clean()
                if clientForm.is_valid():
                    client = clientForm.save(commit=False)
            elif company:
                # organisationForm may be invalid because company is a new one
                organisationForm.data = organisationForm.data.copy()
                organisationForm.data["organisation-company"] = company.id  # Inject company in organisation form
                organisationForm.full_clean()
                if organisationForm.is_valid():
                    organisation = organisationForm.save()
                    clientForm.data = clientForm.data.copy()
                    clientForm.data["client-organisation"] = organisation.id  # Inject organisation in client form
                    clientForm.full_clean()
                    if clientForm.is_valid():
                        client = clientForm.save(commit=False)

        # If everything is alright, save the client and create response
        if client:
            # Add contact if defined
            if contact:
                client.contact = contact
            client.active = True
            client.save()
            result["success"] = True
            result["client_id"] = client.id
            result["client_name"] = str(client)

    else:
        # Unbound forms for GET requests
        clientForm = ClientForm(prefix="client")
        organisationForm = ClientOrganisationForm(prefix="organisation")
        companyForm = CompanyForm(prefix="company")
        contactForm = ContactForm(prefix="contact")

    # Render form
    result["form"] = template.render({ "clientForm": clientForm,
                                       "organisationForm": organisationForm,
                                       "companyForm": companyForm ,
                                       "contactForm": contactForm})

    return HttpResponse(json.dumps(result), content_type="application/json")


@pydici_non_public
@pydici_feature("3rdparties")
def clientOrganisation(request, client_organisation_id=None):
    """Client creation or modification"""
    clientOrganisation = None
    try:
        if client_organisation_id:
            clientOrganisation = ClientOrganisation.objects.get(id=client_organisation_id)
    except ClientOrganisation.DoesNotExist:
        pass

    if request.method == "POST":
        if clientOrganisation:
            form = ClientOrganisationForm(request.POST, instance=clientOrganisation)
        else:
            form = ClientOrganisationForm(request.POST)
        if form.is_valid():
            clientOrganisation = form.save()
            clientOrganisation.save()
            return HttpResponseRedirect(reverse("crm:company_detail", args=[clientOrganisation.company.id]))
    else:
        if clientOrganisation:
            form = ClientOrganisationForm(instance=clientOrganisation)  # A form that edit current client organisation
        else:
            form = ClientOrganisationForm()  # An unbound form

    return render(request, "crm/client_organisation.html", {"client_organisation": clientOrganisation,
                                                            "form": form,
                                                            "user": request.user})


@pydici_non_public
@pydici_feature("3rdparties")
def company(request, company_id=None):
    """Client creation or modification"""
    company = None
    try:
        if company_id:
            company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        pass

    if request.method == "POST":
        if company:
            form = CompanyForm(request.POST, instance=company)
        else:
            form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save()
            company.save()
            return HttpResponseRedirect(reverse("crm:company_detail", args=[company.id]))
    else:
        if company:
            form = CompanyForm(instance=company)  # A form that edit current company
        else:
            form = CompanyForm()  # An unbound form

    return render(request, "crm/clientcompany.html", {"company": company,
                                                      "form": form,
                                                      "user": request.user})


@pydici_non_public
@pydici_feature("3rdparties")
def company_detail(request, company_id):
    """Home page of client company"""
    company = Company.objects.get(id=company_id)
    subsidiary = get_subsidiary_from_session(request)
    data_for_other_subsidiaries = False

    # Find leads of this company
    leads = Lead.objects.filter(client__organisation__company=company)
    if subsidiary:
        if leads.exclude(subsidiary=subsidiary).exists():
            data_for_other_subsidiaries = True
        leads = leads.filter(subsidiary=subsidiary)
    leads = leads.order_by("client", "state", "start_date")

    # Statistics on won/lost etc.
    states = dict(Lead.STATES)
    leads_stat = leads.values("state").order_by("state").annotate(count=Count("state"))
    leads_stat = [[mark_safe(states[s['state']]), s['count']] for s in leads_stat]  # Use state label

    # Find consultant that work (=declare timesheet) for this company
    consultants = Consultant.objects.filter(timesheet__mission__lead__client__organisation__company=company).distinct().order_by("company", "subcontractor")
    if subsidiary:
        consultants = consultants.filter(company=subsidiary)

    # Gather contacts for this company
    business_contacts = Contact.objects.filter(client__organisation__company=company).distinct()
    mission_contacts = Contact.objects.filter(missioncontact__company=company).distinct()
    administrative_contacts = AdministrativeContact.objects.filter(company=company)

    # Won rate
    try:
        won_rate = 100 * leads.filter(state="WON").count() / leads.filter(state__in=("LOST", "FORGIVEN", "WON")).count()
        won_rate = round(won_rate, 1)
    except ZeroDivisionError:
        won_rate = 0
    try:
        overall_won_rate = 100 * Lead.objects.filter(state="WON").count() / Lead.objects.filter(state__in=("LOST", "FORGIVEN", "WON")).count()
    except ZeroDivisionError:
        overall_won_rate = 0

    # Billing stats
    today = date.today()
    company_bills = ClientBill.objects.filter(lead__client__organisation__company=company)
    if subsidiary:
        company_bills = company_bills.filter(lead__subsidiary=subsidiary)
    bills_stat = [
        [_("overdue"), company_bills.filter(state="1_SENT").filter(due_date__lte=today).count()],
        [_("soon due"), company_bills.filter(state="1_SENT").filter(due_date__gt=today).filter(due_date__lte=(today + timedelta(15))).count()],
        [_("last 12 months"), company_bills.filter(state="2_PAID").filter(payment_date__gt=(today - timedelta(12 * 30))).count()]
    ]
    bills_stat_count = sum([i[1] for i in bills_stat])

    # Sales stats
    sales = int(company.sales(subsidiary=subsidiary))
    sales_last_year = int(company.sales(onlyLastYear=True, subsidiary=subsidiary))
    supplier_billing = int(company.supplier_billing(subsidiary=subsidiary))
    direct_sales = sales - supplier_billing

    # Other companies
    companies = Company.objects.filter(clientorganisation__client__id__isnull=False).distinct()

    return render(request, "crm/clientcompany_detail.html",
                  {"company": company,
                   "lead_count": leads.count(),
                   "leads_stat": json.dumps(leads_stat),
                   "won_rate": won_rate,
                   "overall_won_rate": overall_won_rate,
                   "bills_stat": json.dumps(bills_stat),
                   "bills_stat_count": bills_stat_count,
                   "leads": leads,
                   "sales": sales,
                   "supplier_billing" : supplier_billing,
                   "direct_sales": direct_sales,
                   "consultants": consultants,
                   "business_contacts": business_contacts,
                   "mission_contacts": mission_contacts,
                   "administrative_contacts": administrative_contacts,
                   "contacts_count" : business_contacts.count() + mission_contacts.count() + administrative_contacts.count(),
                   "clients": Client.objects.filter(organisation__company=company).select_related(),
                   "lead_data_url": reverse('leads:client_company_lead_table_DT', args=[company.id,]),
                   "mission_data_url": reverse('staffing:client_company_mission_table_DT', args=[company.id,]),
                   "data_for_other_subsidiaries": data_for_other_subsidiaries,
                   "companies": companies,
                   "sales_last_year": sales_last_year
                  })


@pydici_non_public
@pydici_feature("3rdparties")
def company_rates_margin(request, company_id):
    """ajax fragment that display useful stats about margin and rates for this company"""
    company = Company.objects.get(id=company_id)

    return render(request, "crm/_clientcompany_rates_margin.html",
        {"company": company,
         "clients": Client.objects.filter(organisation__company=company).select_related(),
         "profiles": ConsultantProfile.objects.all().order_by("level")})


@pydici_non_public
@pydici_feature("3rdparties")
def company_billing(request, company_id, subsidiary=None):
    company = Company.objects.get(id=company_id)
    subsidiary = get_subsidiary_from_session(request)
    # Find leads of this company
    leads = Lead.objects.filter(client__organisation__company=company)
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)
    leads = leads.order_by("client", "state", "start_date")
    leads = leads.select_related().prefetch_related("clientbill_set", "supplierbill_set")
    return render(request, "crm/_clientcompany_billing.html",
                            {"company": company,
                             "leads": leads})


@pydici_non_public
@pydici_feature("reports")
def company_pivotable(request, company_id=None):
    """Pivot table for a given company with detail"""
    data = []
    dateFormat = "%Y%m%d"
    startDate = endDate = None
    try:
        startDate = request.GET.get("start")
        endDate = request.GET.get("end", None)
        if startDate:
            startDate = datetime.strptime(startDate, dateFormat)
        else:
            startDate = datetime.now() - timedelta(365)  # Default to 1 year. It is often enough.
        if endDate:
            endDate = datetime.strptime(endDate, dateFormat)
    except ValueError:
        pass

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return Http404()
    for lead in Lead.objects.filter(client__organisation__company=company):
        clientName = str(lead.client)
        for mission in lead.mission_set.all():
            missionData = mission.pivotable_data(startDate=startDate, endDate=endDate)
            for item in missionData:
                item[_("client")] = clientName
            data.extend(missionData)

    derivedAttributes = []

    return render(request, "crm/company_pivotable.html", {"data": json.dumps(data),
                                                          "derivedAttributes": derivedAttributes,
                                                          "company": company,
                                                          "startDate": startDate,
                                                          "endDate": endDate })


@pydici_non_public
@pydici_feature("3rdparties")
def company_list(request):
    """Client company list"""
    companies = Company.objects.filter(clientorganisation__client__id__isnull=False).distinct()
    return render(request, "crm/clientcompany_list.html",
                  {"companies": list(companies)})


@pydici_non_public
@pydici_feature("3rdparties")
@cache_page(60 * 60 * 24)
def graph_company_sales(request, onlyLastYear=False, subsidiary_id=None):
    """Sales repartition per company"""
    graph_data = []
    labels = []
    small_clients_amount = 0
    clientBills = ClientBill.objects.filter(state__in=("1_SENT", "2_PAID"))
    if subsidiary_id:
        subsidiary = Subsidiary.objects.get(id=subsidiary_id)
        clientBills = clientBills.filter(lead__subsidiary=subsidiary)
    else:
        subsidiary = None

    minDate = list(clientBills.aggregate(Min("creation_date")).values())[0]
    if onlyLastYear:
        clientBills = clientBills.filter(creation_date__gt=(date.today() - timedelta(365)))

    clientBills = clientBills.values("lead__client__organisation__company__name")
    clientBills = clientBills.order_by("lead__client__organisation__company").annotate(Sum("amount"))
    data = clientBills.order_by("amount__sum").reverse()
    small_clients = data[8:]
    data = data[0:8]
    for i in data:
        graph_data.append([i["lead__client__organisation__company__name"], int(i["amount__sum"]/1000)])
    # If there are more than 8 clients, we aggregate all the "small clients" under "Others"
    if len(small_clients) > 0:
        for i in small_clients:
            small_clients_amount += int(i["amount__sum"]/1000)
        graph_data.append([_("Others"), small_clients_amount])

    if sum(graph_data, []):  # Test if list contains other things that empty lists
        graph_data = json.dumps(graph_data)
    else:
        # If graph_data is only a bunch of emty list, set it to None
        graph_data = None
    return render(request, "crm/graph_company_sales.html",
                  {"graph_data": graph_data,
                   "series_colors": COLORS,
                   "only_last_year": onlyLastYear,
                   "min_date": minDate,
                   "subsidiary": subsidiary,
                   "labels": json.dumps(labels),
                   "user": request.user})


@pydici_non_public
@pydici_feature("3rdparties")
@cache_page(60 * 60)
def graph_company_business_activity(request, company_id):
    """Business activity (leads and bills) for a company"""
    billsData = dict()
    lostLeadsData = dict()
    preSalesData = dict()
    wonLeadsData = dict()
    company = Company.objects.get(id=company_id)
    subsidiary = get_subsidiary_from_session(request)

    bills = ClientBill.objects.filter(lead__client__organisation__company=company, state__in=("1_SENT", "2_PAID"))
    if subsidiary:
        bills = bills.filter(lead__subsidiary=subsidiary)
    for bill in bills:
        kdate = bill.creation_date.replace(day=1)
        if kdate in billsData:
            billsData[kdate] += int(float(bill.amount) / 1000)
        else:
            billsData[kdate] = int(float(bill.amount) / 1000)

    leads = Lead.objects.filter(client__organisation__company=company)
    if subsidiary:
        leads = leads.filter(subsidiary=subsidiary)
    for lead in leads:
        kdate = lead.creation_date.date().replace(day=1)
        for data in (lostLeadsData, wonLeadsData, preSalesData, billsData):
            data[kdate] = data.get(kdate, 0)  # Default to 0 to avoid stacking weirdness in graph
        if lead.state == "WON":
            wonLeadsData[kdate] += 1
        elif lead.state in ("LOST", "FORGIVEN"):
            lostLeadsData[kdate] += 1
        else:
            preSalesData[kdate] += 1

    graph_data = [
        ["x_billing"] + [d.isoformat() for d in list(billsData.keys())],
        ["x_leads"] + [d.isoformat() for d in list(wonLeadsData.keys())],
        ["y_billing"] + list(billsData.values()),
        ["y_lost_leads"] + list(lostLeadsData.values()),
        ["y_won_leads"] + list(wonLeadsData.values()),
        ["y_presales_leads"] + list(preSalesData.values()),
    ]

    return render(request, "crm/graph_company_business_activity.html",
                  {"graph_data": json.dumps(graph_data),
                   "user": request.user})
