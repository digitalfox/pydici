# coding:utf-8
"""
CRM form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.utils.encoding import smart_unicode
from django.core.urlresolvers import reverse

from django_select2 import AutoModelSelect2Field, AutoModelSelect2MultipleField
from crispy_forms.layout import Layout, Div, Column
from crispy_forms.bootstrap import AppendedText

from core.forms import PydiciSelect2Field
from crm.models import Client, BusinessBroker, Supplier, MissionContact, ClientOrganisation, Contact, Company, AdministrativeContact
from people.forms import ConsultantChoices, ConsultantMChoices
from core.utils import capitalize
from core.forms import PydiciCrispyModelForm


class ClientChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = Client.objects
    search_fields = ["organisation__name__icontains", "organisation__company__name__icontains", "contact__name__icontains"]

    def get_queryset(self):
        return Client.objects.order_by("-active")

    def label_from_instance(self, obj):
        if obj.active:
            return smart_unicode(unicode(obj))
        else:
            return smart_unicode(ugettext("%s (inactive)" % obj))



class ThirdPartyChoices(PydiciSelect2Field, AutoModelSelect2Field):
    """Common field for all models based on couple (company, contact)"""
    search_fields = ["contact__name__icontains", "company__name__icontains"]


class BusinessBrokerChoices(ThirdPartyChoices):
    queryset = BusinessBroker.objects


class SupplierChoices(ThirdPartyChoices):
    queryset = Supplier.objects


class MissionContactChoices(ThirdPartyChoices):
    queryset = MissionContact.objects


class MissionContactMChoices(PydiciSelect2Field, AutoModelSelect2MultipleField):
    queryset = MissionContact.objects
    search_fields = ThirdPartyChoices.search_fields


class ContactChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = Contact.objects
    search_fields = ["name__icontains", "email__icontains", "function__icontains", "client__organisation__company__name__icontains",
                     "client__organisation__name__icontains"]


class ContactMChoices(PydiciSelect2Field, AutoModelSelect2MultipleField):
    queryset = Contact.objects
    search_fields = ["name__icontains", "email__icontains", "function__icontains", "client__organisation__company__name__icontains",
                     "client__organisation__name__icontains"]


class ClientOrganisationChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = ClientOrganisation.objects
    search_fields = ["name__icontains", "company__name__icontains", "company__code__icontains"]


class CompanyChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = Company.objects
    search_fields = ["name__icontains", "code__icontains"]


class ClientForm(PydiciCrispyModelForm):
    class Meta:
        model = Client

    organisation = ClientOrganisationChoices()
    contact = ContactChoices(required=False)

    def __init__(self, *args, **kwargs):
        super(ClientForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column(AppendedText("organisation", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.clientOrganisation")),
                                               "expectations", css_class="col-md-6"),
                                        Column(AppendedText("contact", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add")),
                                               "alignment", css_class="col-md-6"),
                                        css_class="row"),
                                    "active",
                                    self.submit)


class ClientOrganisationForm(PydiciCrispyModelForm):
    class Meta:
        model = ClientOrganisation

    company = CompanyChoices(label=_("Company"))

    def __init__(self, *args, **kwargs):
        super(ClientOrganisationForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("name", AppendedText("company", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company")), css_class="col-md-6"),
                                        Column(css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)


class CompanyForm(PydiciCrispyModelForm):
    class Meta:
        model = Company

    businessOwner = ConsultantChoices(label=_("Business Owner"))

    def __init__(self, *args, **kwargs):
        super(CompanyForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("name", "code", "businessOwner", "web", css_class="col-md-6"),
                                        Column(css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)


class ContactForm(PydiciCrispyModelForm):
    class Meta:
        model = Contact

    contact_points = ConsultantMChoices(label=_("Points of contact"))
    def __init__(self, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("name", "email", "function", "contact_points", css_class="col-md-6"),
                                        Column("mobile_phone", "phone", "fax", css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)

    def clean_name(self):
        return capitalize(self.cleaned_data["name"])


class MissionContactForm(PydiciCrispyModelForm):
    class Meta:
        model = MissionContact

    contact = ContactChoices()
    company = CompanyChoices(label=_("Company"))

    def __init__(self, *args, **kwargs):
        super(MissionContactForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column(AppendedText("contact", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add")),
                                               css_class="col-md-6"),
                                        Column(AppendedText("company", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company")),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)


class BusinessBrokerForm(PydiciCrispyModelForm):
    class Meta:
        model = BusinessBroker

    contact = ContactChoices()
    company = CompanyChoices(label=_("Company"))

    def __init__(self, *args, **kwargs):
        super(BusinessBrokerForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column(AppendedText("contact", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add")),
                                               css_class="col-md-6"),
                                        Column(AppendedText("company", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company")),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)


class AdministrativeContactForm(PydiciCrispyModelForm):
    class Meta:
        model = AdministrativeContact

    contact = ContactChoices(required=False)
    company = CompanyChoices(label=_("Company"))

    def __init__(self, *args, **kwargs):
        super(AdministrativeContactForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("function", "default_phone", "default_mail",
                                               css_class="col-md-6"),
                                        Column(AppendedText("company", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company")),
                                               "default_fax",
                                               AppendedText("contact", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add")),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)
