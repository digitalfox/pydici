# coding:utf-8
"""
Leads form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.forms import models
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Column, Fieldset, Field
from crispy_forms.bootstrap import AppendedText, TabHolder, Tab
from django_select2 import AutoModelSelect2Field


from leads.models import Lead
from people.forms import ConsultantChoices, ConsultantMChoices, SalesManChoices
from crm.forms import ClientChoices, BusinessBrokerChoices
from core.forms import PydiciSelect2Field


class LeadChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = Lead.objects
    search_fields = ["name__icontains", "description__icontains", "action__icontains",
                     "responsible__name__icontains", "responsible__trigramme__icontains",
                     "salesman__name__icontains", "salesman__trigramme__icontains",
                     "client__contact__name__icontains", "client__organisation__company__name__icontains",
                     "client__organisation__name__icontains",
                     "staffing__trigramme__icontains", "staffing__name__icontains",
                     "deal_id__icontains", "client_deal_id__icontains"]


class LeadForm(models.ModelForm):
    class Meta:
        model = Lead

    responsible = ConsultantChoices(required=False, label=_("Responsible"))
    salesman = SalesManChoices(required=False, label=_("Salesman"))
    business_broker = BusinessBrokerChoices(required=False, label=_("Business broker"))
    paying_authority = BusinessBrokerChoices(required=False, label=_("Paying authority"))
    client = ClientChoices()
    staffing = ConsultantMChoices(required=False)

    def __init__(self, *args, **kwargs):
        super(LeadForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        submit = Submit("Submit", _("Save"))
        submit.field_classes = "btn btn-default"
        self.helper.layout = Layout(TabHolder(Tab(_("Identification"), "name",
                                                  AppendedText("client", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.client")),
                                                  "subsidiary", "description", "action"),
                                              Tab(_("State and tracking"), Div(Column("responsible", Field("due_date", placeholder=_("Due date for next next"), css_class="datepicker"),
                                                                                      Field("start_date", placeholder=_("Date of the operational start"), css_class="datepicker"),
                                                                                      css_class='col-md-6'),
                                                                               Column(Field("deal_id", placeholder=_("Leave blank to auto generate")),
                                                                                      Field("client_deal_id", placeholder=_("Internal client reference")), "state", css_class='col-md-6'))),
                                              Tab(_("Commercial"), Div(Column(AppendedText("sales", "k€"), "salesman", css_class='col-md-6'),
                                                                       Column("business_broker", "paying_authority", css_class='col-md-6'))),
                                              Tab(_("Staffing"), "staffing", Field("external_staffing", placeholder=_("People outside company that could contribute..."))),),
                                    Fieldset("", "send_email"),
                                    Field("creation_date", type="hidden"),
                                    submit)

    def clean_sales(self):
        """Ensure sale amount is defined at lead when commercial proposition has been sent"""
        if self.cleaned_data["sales"] or self.data["state"] in ('QUALIF', 'WRITE_OFFER', 'SLEEPING', 'LOST', 'FORGIVEN'):
            # Sales is defined or we are in early step, nothing to say
            return self.cleaned_data["sales"]
        else:
            # We can't tolerate that sale amount is not known at this step of the process
            raise ValidationError(_("Sales amount must be defined at this step of the commercial process"))

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
