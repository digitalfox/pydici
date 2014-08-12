# coding:utf-8
"""
CRM form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from django_select2 import AutoModelSelect2Field, AutoModelSelect2MultipleField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Column
from crispy_forms.bootstrap import AppendedText

from core.forms import PydiciSelect2Field
from crm.models import Client, BusinessBroker, Supplier, MissionContact, ClientOrganisation, Contact


class ClientChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = Client.objects.filter(active=True)
    search_fields = ["organisation__name__icontains", "organisation__company__name__icontains", "contact__name__icontains"]


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


class ClientForm(models.ModelForm):
    class Meta:
        model = Client

    organisation = ClientOrganisationChoices()
    contact = ContactChoices(required=False)

    def __init__(self, *args, **kwargs):
        super(ClientForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        submit = Submit("Submit", _("Save"))
        submit.field_classes = "btn btn-default"
        self.helper.layout = Layout(Div(Column(AppendedText("organisation", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("admin:crm_clientorganisation_add")),
                                               "expectations", css_class="col-md-6"),
                                        Column("contact", "alignment", css_class="col-md-6"),
                                        css_class="row"),
                                    "active",
                                    submit)
