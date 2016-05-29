# coding:utf-8
"""
Leads form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_unicode
from django import forms

from crispy_forms.layout import Layout, Div, Column, Fieldset, Field
from crispy_forms.bootstrap import AppendedText, TabHolder, Tab
#from django_select2 import AutoModelSelect2Field
from taggit.forms import TagField


from leads.models import Lead
from people.models import Consultant, SalesMan
from crm.models import Client, BusinessBroker
from people.forms import ConsultantChoices, ConsultantMChoices, SalesManChoices
from crm.forms import ClientChoices, BusinessBrokerChoices
from core.forms import PydiciSelect2Field, PydiciCrispyModelForm


# class LeadChoices(PydiciSelect2Field, AutoModelSelect2Field):
#     queryset = Lead.objects.distinct()
#     search_fields = ["name__icontains", "description__icontains", "action__icontains",
#                      "responsible__name__icontains", "responsible__trigramme__icontains",
#                      "salesman__name__icontains", "salesman__trigramme__icontains",
#                      "client__contact__name__icontains", "client__organisation__company__name__icontains",
#                      "client__organisation__name__icontains",
#                      "staffing__trigramme__icontains", "staffing__name__icontains",
#                      "deal_id__icontains", "client_deal_id__icontains"]
#
#     def label_from_instance(self, obj):
#         return smart_unicode("%s (%s)" % (unicode(obj), obj.deal_id))
#
#
# class CurrentLeadChoices(LeadChoices):
#     """Limit Leads to those who have active (non archived) missions"""
#     queryset = Lead.objects.filter(mission__active=True).distinct()
#
#
class LeadForm(PydiciCrispyModelForm):
    class Meta:
        model = Lead
        exclude = ["external_id", "creation_date"]

    responsible = forms.ModelChoiceField(required=False, label=_("Responsible"), widget=ConsultantChoices, queryset=Consultant.objects.all())
    salesman = forms.ModelChoiceField(required=False, label=_("Salesman"), widget=SalesManChoices, queryset=SalesMan.objects.all())
    business_broker = forms.ModelChoiceField(required=False, label=_("Business broker"), widget=BusinessBrokerChoices, queryset=BusinessBroker.objects.all())
    paying_authority = forms.ModelChoiceField(required=False, label=_("Paying authority"), widget=BusinessBrokerChoices, queryset=BusinessBroker.objects.all())
    client = forms.ModelChoiceField(widget=ClientChoices, queryset=Client.objects.all())
    staffing = forms.ModelMultipleChoiceField(widget=ConsultantMChoices, required=False, queryset=Consultant.objects.all())
    tags = TagField(label="", required=False)

    def __init__(self, *args, **kwargs):
        super(LeadForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(TabHolder(Tab(_("Identification"), Field("name", placeholder=mark_safe(_("Name of the lead. don't include client name"))),
                                                  AppendedText("client", "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("crm.views.client")),
                                                  "subsidiary", "description", Field("action", placeholder=_("Next commercial action to be done"))),
                                              Tab(_("State and tracking"), Div(Column("responsible", Field("due_date", placeholder=_("Due date for next step"), css_class="datepicker"),
                                                                                      Field("start_date", placeholder=_("Date of the operational start"), css_class="datepicker"),
                                                                                      css_class='col-md-6'),
                                                                               Column(Field("deal_id", placeholder=_("Leave blank to auto generate")),
                                                                                      Field("client_deal_id", placeholder=_("Internal client reference")), "state", css_class='col-md-6'))),
                                              Tab(_("Commercial"), Div(Column(AppendedText("sales", "k€"), "salesman", css_class='col-md-6'),
                                                                       Column(AppendedText("business_broker",
                                                                                           "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("businessbroker_add"),
                                                                                           placeholder=_("If the leads was brought by a third party")),
                                                                              AppendedText("paying_authority",
                                                                                           "<a href='%s' target='_blank'><span class='glyphicon glyphicon-plus'></span></a>" % reverse("businessbroker_add"),
                                                                                           placeholder=_("If payment is done by a third party")), css_class='col-md-6'))),
                                              Tab(_("Staffing"), Div(Field("staffing", placeholder=_("People that could contribute...")),
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
