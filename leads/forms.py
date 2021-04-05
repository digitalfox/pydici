# coding:utf-8
"""
Leads form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_text
from django import forms

from crispy_forms.layout import Layout, Div, Column, Fieldset, Field, HTML, Row
from crispy_forms.bootstrap import AppendedText, TabHolder, Tab, StrictButton, FieldWithButtons
from django_select2.forms import ModelSelect2Widget
from taggit.forms import TagField


from leads.models import Lead
from people.models import Consultant, SalesMan
from crm.models import Client, BusinessBroker
from people.forms import ConsultantChoices, ConsultantMChoices, SalesManChoices
from crm.forms import ClientChoices, BusinessBrokerChoices
from core.forms import PydiciCrispyModelForm, PydiciSelect2WidgetMixin


class LeadChoices(PydiciSelect2WidgetMixin, ModelSelect2Widget):
    model = Lead
    search_fields = ["name__icontains", "description__icontains", "action__icontains",
                     "responsible__name__icontains", "responsible__trigramme__icontains",
                     "salesman__name__icontains", "salesman__trigramme__icontains",
                     "client__contact__name__icontains", "client__organisation__company__name__icontains",
                     "client__organisation__name__icontains",
                     "staffing__trigramme__icontains", "staffing__name__icontains",
                     "deal_id__icontains", "client_deal_id__icontains"]

    def get_queryset(self):
        return Lead.objects.distinct()

    def label_from_instance(self, obj):
        return smart_text("%s (%s)" % (str(obj), obj.deal_id))


class CurrentLeadChoices(LeadChoices):
    """Limit Leads to those who have active (non archived) missions or in active state"""
    def get_queryset(self):
        return (Lead.objects.filter(mission__active=True) | Lead.objects.active()).distinct()


class SubcontractorLeadChoices(CurrentLeadChoices):
    """Dedicated  class to allow subcontractor to select leads limited to its scope"""
    model = Lead
    search_fields = LeadChoices.search_fields
    subcontractor = None

    def __init__(self, *args, **kwargs):
        self.subcontractor = kwargs.pop("subcontractor", None)
        super(SubcontractorLeadChoices, self).__init__(*args, **kwargs)
        self.data_view =  "pydici-select2-view-subcontractor"  # override to use subcontractor endpoint for widget completion

    def get_queryset(self):
        qs = super(CurrentLeadChoices, self).get_queryset()
        qs = qs.filter(mission__staffing__consultant = self.subcontractor)
        return qs.distinct()


class LeadForm(PydiciCrispyModelForm):
    class Meta:
        model = Lead
        exclude = ["external_id", "creation_date"]

    responsible = forms.ModelChoiceField(required=False, label=_("Responsible"), widget=ConsultantChoices, queryset=Consultant.objects.all())
    salesman = forms.ModelChoiceField(required=False, label=_("Salesman"), widget=SalesManChoices, queryset=SalesMan.objects.all())
    business_broker = forms.ModelChoiceField(required=False, label=_("Business broker"), widget=BusinessBrokerChoices(attrs={"data-placeholder": _("If the leads was brought by a third party")}), queryset=BusinessBroker.objects.all())
    paying_authority = forms.ModelChoiceField(required=False, label=_("Paying authority"), widget=BusinessBrokerChoices(attrs={"data-placeholder": _("If payment is done by a third party")}), queryset=BusinessBroker.objects.all())
    client = forms.ModelChoiceField(widget=ClientChoices, queryset=Client.objects.all())
    staffing = forms.ModelMultipleChoiceField(widget=ConsultantMChoices, required=False, queryset=Consultant.objects.all())
    tags = TagField(label="", required=False)

    def __init__(self, *args, **kwargs):
        super(LeadForm, self).__init__(*args, **kwargs)
        clientPopupUrl = reverse("crm:client_organisation_company_popup")
        self.helper.layout = Layout(TabHolder(Tab(_("Identification"),
                                                  Column(Field("name", placeholder=mark_safe(_("Name of the lead. don't include client name"))), css_class="col-md-12"),
                                                  Row(Column(FieldWithButtons("client", HTML(
                                                          "<a role='button' class='btn btn-primary' href='%s' data-remote='false' data-bs-toggle='modal' data-bs-target='#clientModal'><i class='bi bi-plus'></i></a>" % clientPopupUrl)),
                                                          css_class="col-6"),
                                                      Column("subsidiary", css_class="col-md-6 col-12"),),
                                                  Row(Column("description", css_class="col-md-6 col-12"),
                                                      Column("administrative_notes", css_class="col-md-6 col-12")),
                                                  Column(Field("action", placeholder=_("Next commercial action to be done")), css_class="col-md-6")),
                                              Tab(_("State and tracking"),
                                                  Row(Column("responsible", css_class="col-md-6 col-12"),
                                                      Column(Field("deal_id", placeholder=_("Leave blank to auto generate")), css_class="col-md-6 col-12")),
                                                  Row(Column(Field("due_date", placeholder=_("Due date for next step"), css_class="datepicker"), css_class="col-md-6 col-12"),
                                                      Column(Field("client_deal_id", placeholder=_("Internal client reference")), css_class="col-md-6 col-12")),
                                                  Row(Column(Field("start_date", placeholder=_("Date of the operational start"), css_class="datepicker"), css_class="col-md-6 col-12"),
                                                      Column("state", css_class='col-md-6'))),
                                              Tab(_("Commercial"), Row(Column(AppendedText("sales", "k€"), css_class="col-md-6"),
                                                                       Column(FieldWithButtons("business_broker",
                                                                                           HTML("<a role='button' class='btn btn-primary' href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm:businessbroker_create"))),css_class="col-md-6")),
                                                                   Row(Column("salesman", css_class="col-md-6"),
                                                                       Column(FieldWithButtons("paying_authority",
                                                                                           HTML("<a role='button' class='btn btn-primary' href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm:businessbroker_create")))))),
                                              Tab(_("Staffing"), Column(Field("staffing", placeholder=_("People that could contribute...")),
                                                                        Field("external_staffing", placeholder=_("People outside company that could contribute...")),
                                                                        css_class="col-md-6"))),
                                    Fieldset("", "send_email"),
                                    Field("tags", css_class="hide"),  # Don't use type=hidden, it breaks tag parsing.
                                    self.submit)

    def clean_sales(self):
        """Ensure sale amount is defined at lead when commercial proposition has been sent"""
        if self.cleaned_data["sales"] or self.data["state"] in ('QUALIF', 'WRITE_OFFER', 'SLEEPING', 'LOST', 'FORGIVEN'):
            # Sales is defined or we are in early step, nothing to say
            return self.cleaned_data["sales"]
        else:
            # We can't tolerate that sale amount is not known at this step of the process
            raise ValidationError(_("Sales amount must be defined at this step of the commercial process"))


    def clean_start_date(self):
        """Ensure start_date amount is defined at lead when commercial proposition has been sent"""
        if self.cleaned_data["start_date"] or self.data["state"] in ('QUALIF', 'WRITE_OFFER', 'SLEEPING', 'LOST', 'FORGIVEN'):
            # Start_date is defined or we are in early step, nothing to say
            return self.cleaned_data["start_date"]
        else:
            # We can't tolerate that start_date is not known at this step of the process
            raise ValidationError(_("Start date must be defined at this step of the commercial process"))

    def clean_deal_id(self):
        """Ensure deal id is unique.
        Cannot be done at database level because we tolerate null/blank value and all db engines are
        not consistent in the way they handle that. SQL ISO is really fuzzy about that. Sad"""
        if not self.cleaned_data["deal_id"]:
            # No value, no pb :-)
            return self.cleaned_data["deal_id"]
        else:
            if Lead.objects.filter(deal_id=self.cleaned_data["deal_id"]).exclude(id=self.instance.id).exists():
                raise ValidationError(_("Deal id must be unique. Use another value or let the field blank for automatic computation"))
            else:
                return self.cleaned_data["deal_id"]
