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

from django.forms.widgets import Textarea

from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from crispy_forms.layout import Layout, Div, Column, Fieldset
from crispy_forms.bootstrap import AppendedText, FieldWithButtons, StrictButton, Tab, TabHolder

from crm.models import Client, BusinessBroker, Supplier, MissionContact, ClientOrganisation, Contact, Company, AdministrativeContact
from people.forms import ConsultantChoices, ConsultantMChoices
from core.utils import capitalize
from core.forms import PydiciCrispyModelForm


class ClientChoices(ModelSelect2Widget):
    model = Client
    search_fields = ["organisation__name__icontains", "organisation__company__name__icontains", "contact__name__icontains"]

    def get_queryset(self):
        return Client.objects.order_by("-active")

    def label_from_instance(self, obj):
        if obj.active:
            return smart_unicode(unicode(obj))
        else:
            return smart_unicode(ugettext(u"%s (inactive)" % obj))


class ThirdPartyChoices(ModelSelect2Widget):
     """Common field for all models based on couple (company, contact)"""
     search_fields = ["contact__name__icontains", "company__name__icontains"]


class BusinessBrokerChoices(ThirdPartyChoices):
    model = BusinessBroker


class SupplierChoices(ThirdPartyChoices):
    model = Supplier


class MissionContactChoices(ThirdPartyChoices):
    model = MissionContact


class MissionContactMChoices(ModelSelect2MultipleWidget):
    model = MissionContact
    search_fields = ThirdPartyChoices.search_fields


class ContactChoices(ModelSelect2Widget):
    model = Contact
    search_fields = ["name__icontains", "email__icontains", "function__icontains", "client__organisation__company__name__icontains",
                     "client__organisation__name__icontains"]


class ContactMChoices(ModelSelect2MultipleWidget):
    model = Contact
    search_fields = ["name__icontains", "email__icontains", "function__icontains", "client__organisation__company__name__icontains",
                     "client__organisation__name__icontains"]


class ClientOrganisationChoices(ModelSelect2Widget):
    model = ClientOrganisation
    search_fields = ["name__icontains", "company__name__icontains", "company__code__icontains"]


class CompanyChoices(ModelSelect2Widget):
    model = Company
    search_fields = ["name__icontains", "code__icontains"]


class ClientForm(PydiciCrispyModelForm):
    class Meta:
        model = Client
        fields = "__all__"
        widgets = { "contact": ContactChoices,
                    "organisation": ClientOrganisationChoices}


    def __init__(self, *args, **kwargs):
        super(ClientForm, self).__init__(*args, **kwargs)
        self.helper.form_action = reverse("crm.views.client")
        self.helper.layout = Layout(Div(Column(AppendedText("organisation", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.clientOrganisation")),
                                               "expectations", css_class="col-md-6"),
                                        Column(AppendedText("contact", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add")),
                                               "alignment", css_class="col-md-6"),
                                        css_class="row"),
                                    "active",
                                    self.submit)
        self.inline_helper.layout = Layout(Div(Column("expectations",
                                                    FieldWithButtons("organisation",
                                                        StrictButton("""<a href='#' onclick='$("#organisationForm").show("slow"); $("#organisation_input_group").hide("slow")'><span class='glyphicon glyphicon-plus'></span></a>"""), css_id="organisation_input_group"),
                                                    css_class="col-md-6"),
                                                Column("alignment",
                                                    FieldWithButtons("contact",
                                                        StrictButton("""<a href='#' onclick='$("#contactForm").show("slow"); $("#contact_input_group").hide("slow")'><span class='glyphicon glyphicon-plus'></span></a>"""), css_id="contact_input_group"),
                                                    css_class="col-md-6"),
                                                css_class="row"),
                                    )


class ClientOrganisationForm(PydiciCrispyModelForm):
    class Meta:
        model = ClientOrganisation
        fields = "__all__"
        widgets = {"company": CompanyChoices}


    def __init__(self, *args, **kwargs):
        super(ClientOrganisationForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("name", AppendedText("company", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company")), css_class="col-md-6"),
                                        Column(css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)
        self.inline_helper.layout = Layout(Fieldset(_("Client organisation"),
                                                    Column("name",
                                                        FieldWithButtons("company", StrictButton("""<a href='#' onclick='$("#companyForm").show("slow"); $("#company_input_group").hide("slow")'><span class='glyphicon glyphicon-plus'></span></a>"""), css_id="company_input_group"),
                                                        css_class="col-md-6"),
                                                    Column(css_class="col-md-6"),
                                                    css_class="collapse", css_id="organisationForm"))

class CompanyForm(PydiciCrispyModelForm):
    class Meta:
        model = Company
        exclude = ["external_id",]
        widgets = { "businessOwner" : ConsultantChoices,
                    "billing_street": Textarea(attrs={'cols': 17, 'rows': 2}),
                    "street": Textarea(attrs={'cols': 17, 'rows': 2})}


    def __init__(self, *args, **kwargs):
        super(CompanyForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("name", "code", "businessOwner", "web", css_class="col-md-6"),
                                        Column(TabHolder(Tab(_("Main address"), "street",
                                                             Div(Column("city", css_class="col-md-6"), Column("zipcode", css_class="col-md-6"), css_class="row"),
                                                             "country"),
                                                         Tab(_("Billing address"), "billing_street",
                                                             Div(Column("billing_city", css_class="col-md-6"), Column("billing_zipcode", css_class="col-md-6"), css_class="row"),
                                                             "billing_country"),),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)
        self.inline_helper.layout = Layout(Fieldset(_("Company"),
                                                    Column("name", "code", "businessOwner", "web", css_class="col-md-6"),
                                                    Column(css_class="col-md-6"),
                                                    css_class="collapse", css_id="companyForm"))


class ContactForm(PydiciCrispyModelForm):
    class Meta:
        model = Contact
        exclude = ["external_id",]
        widgets = {"contact_points": ConsultantMChoices}

    def __init__(self, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("name", "email", "function", "contact_points", css_class="col-md-6"),
                                        Column("mobile_phone", "phone", "fax", css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)
        self.inline_helper.layout = Layout(Fieldset(_("Contact"),
                                                    Column("name", "email", "function", "contact_points", css_class="col-md-6"),
                                                    Column("mobile_phone", "phone", "fax", css_class="col-md-6"),
                                                    css_class="collapse", css_id="contactForm"),
                                    )

    def clean_name(self):
        return capitalize(self.cleaned_data["name"])


class MissionContactForm(PydiciCrispyModelForm):
    class Meta:
        model = MissionContact
        fields = "__all__"
        widgets = {"contact": ContactChoices,
                   "company": CompanyChoices}


    def __init__(self, *args, **kwargs):
        super(MissionContactForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column(FieldWithButtons("contact", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add"))),
                                               css_class="col-md-6"),
                                        Column(FieldWithButtons("company", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company"))),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)


class BusinessBrokerForm(PydiciCrispyModelForm):
    class Meta:
        model = BusinessBroker
        fields = "__all__"
        widgets = {"contact": ContactChoices,
                   "company": CompanyChoices}


    def __init__(self, *args, **kwargs):
        super(BusinessBrokerForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column(FieldWithButtons("contact", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add"))),
                                               css_class="col-md-6"),
                                        Column(FieldWithButtons("company", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company"))),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)


class AdministrativeContactForm(PydiciCrispyModelForm):
    class Meta:
        model = AdministrativeContact
        fields = "__all__"
        widgets = {"contact": ContactChoices,
                   "company": CompanyChoices}

    def __init__(self, *args, **kwargs):
        super(AdministrativeContactForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column("function", "default_phone", "default_mail",
                                               css_class="col-md-6"),
                                        Column(FieldWithButtons("company", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company"))),
                                               "default_fax",
                                               FieldWithButtons("contact", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add"))),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)

class SupplierForm(PydiciCrispyModelForm):
    class Meta:
        model = Supplier
        fields = "__all__"
        widgets = {"contact": ContactChoices,
                   "company": CompanyChoices}


    def __init__(self, *args, **kwargs):
        super(SupplierForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column(FieldWithButtons("contact", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("contact_add"))),
                                               css_class="col-md-6"),
                                        Column(FieldWithButtons("company", StrictButton("<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.company"))),
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    self.submit)
