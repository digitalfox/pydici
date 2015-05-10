# coding:utf-8
"""
Staffing form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
import types

from datetime import timedelta, date
from decimal import Decimal

from django import forms
from django.conf import settings
from django.forms.models import BaseInlineFormSet
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.db.models import Min


from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Column, Field
from crispy_forms.bootstrap import AppendedText
from django_select2 import AutoModelSelect2Field, AutoModelSelect2MultipleField, Select2ChoiceField, AutoHeavySelect2Widget, Select2Widget
from django.utils import formats


from staffing.models import Mission, FinancialCondition
from core.forms import PydiciSelect2Field, PydiciCrispyModelForm
from people.forms import ConsultantChoices, ConsultantMChoices
from crm.forms import MissionContactMChoices
from staffing.utils import staffingDates, time_string_for_day_percent, day_percent_for_time_string
from leads.forms import LeadChoices


class MissionChoices(PydiciSelect2Field, AutoModelSelect2Field):
    queryset = Mission.objects
    search_fields = ["deal_id__icontains", "description__icontains", "lead__name__icontains", "lead__deal_id__icontains",
                     "lead__client__organisation__name__icontains", "lead__client__organisation__company__name__icontains"]

    def get_queryset(self):
        return Mission.objects.filter(active=True)

class MissionMChoices(PydiciSelect2Field, AutoModelSelect2MultipleField):
    queryset = Mission.objects
    search_fields = MissionChoices.search_fields

    def get_queryset(self):
        return Mission.objects.filter(active=True)


class StaffingDateChoices(Select2ChoiceField):
    def __init__(self, *args, **kwargs):
        minDate = kwargs.pop("minDate", None)
        if minDate:
            missionDuration = (date.today() - minDate).days / 30
            numberOfMonth = 24 + missionDuration
        else:
            numberOfMonth = 24
        kwargs["choices"] = [(i, formats.date_format(i, format="YEAR_MONTH_FORMAT")) for i in staffingDates(format="datetime", n=numberOfMonth, minDate=minDate)]
        kwargs["choices"].insert(0, ("", ""))  # Add the empty choice for extra empty choices
        super(StaffingDateChoices, self).__init__(*args, **kwargs)


class ConsultantStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields"""

    lowerDayBound = None  # Bound of staffing used to hide past staffing

    def get_queryset(self):
        if not hasattr(self, '_queryset'):
            qs = super(ConsultantStaffingInlineFormset, self).get_queryset()
            if date.today().day > 5:
                self.lowerDayBound = date.today().replace(day=1)
            else:
                lastDayOfPreviousMonth = date.today().replace(day=1) + timedelta(-1)
                self.lowerDayBound = lastDayOfPreviousMonth.replace(day=1)

            qs = qs.filter(mission__active=True,  # Remove archived mission
                           staffing_date__gte=self.lowerDayBound)  # Remove past missions

            self._queryset = qs
        return self._queryset

    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(ConsultantStaffingInlineFormset, self).add_fields(form, index)
        form.fields["mission"] = MissionChoices(label=_("Mission"), widget=AutoHeavySelect2Widget(select2_options={"dropdownAutoWidth": "true",
                                                                                                                   "placeholder": _("Select a mission to add forecast...")}))
        form.fields["mission"].widget.attrs.setdefault("size", 8)  # Reduce default size
        form.fields["staffing_date"] = StaffingDateChoices(widget=Select2Widget(select2_options={"placeholder": _("Select a month...")}),
                                                           minDate=self.lowerDayBound)
        form.fields["charge"].widget.attrs.setdefault("size", 3)  # Reduce default size


class MissionStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields"""
    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(MissionStaffingInlineFormset, self).add_fields(form, index)
        minDate = self.instance.staffing_set.all().aggregate(Min("staffing_date")).values()
        if minDate and minDate[0]:
            minDate = min(minDate[0], date.today())
        else:
            minDate = None
        form.fields["consultant"] = ConsultantChoices(label=_("Consultant"), widget=AutoHeavySelect2Widget(select2_options={"dropdownAutoWidth": "true",
                                                                                                                            "placeholder": _("Select a consultant to add forecast...")}))
        form.fields["staffing_date"] = StaffingDateChoices(widget=Select2Widget(select2_options={"placeholder": _("Select a month...")}),
                                                           minDate=minDate)
        form.fields["charge"].widget.attrs.setdefault("size", 3)  # Reduce default size


class MassStaffingForm(forms.Form):
    """Massive staffing input forms that allow to define same staffing
    for a group of consultant accross different months"""
    def __init__(self, *args, **kwargs):
        staffing_dates = kwargs.pop("staffing_dates", [])
        super(MassStaffingForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields["missions"] = MissionMChoices(label=_("Missions"))
        self.fields["consultants"] = ConsultantMChoices(required=False, label=_("Consultants"))
        self.fields["charge"] = forms.fields.FloatField(label=_("Charge"), min_value=0.25, max_value=31)
        self.fields["comment"] = forms.fields.CharField(label=_("Comment"), max_length=100, required=False)
        self.fields["all_consultants"] = forms.fields.BooleanField(label=_("All active consultants"), required=False)
        self.fields["staffing_dates"] = forms.fields.MultipleChoiceField(label=_("Staffing dates"), choices=staffing_dates)
        submit = Submit("Submit", _("Save"))
        submit.field_classes = "btn btn-default"
        self.helper.layout = Layout(Div(Column("missions", "consultants", "all_consultants", css_class='col-md-6'),
                                        Column("charge", "staffing_dates", "comment", css_class='col-md-6'),
                                        css_class='row'),
                                    submit)


class TimesheetForm(forms.Form):
    """Consultant timesheet form"""
    def __init__(self, *args, **kwargs):
        days = kwargs.pop("days", None)
        missions = kwargs.pop("missions", None)
        forecastTotal = kwargs.pop("forecastTotal", [])
        timesheetTotal = kwargs.pop("timesheetTotal", [])
        holiday_days = kwargs.pop("holiday_days", [])
        showLunchTickets = kwargs.pop("showLunchTickets", True)
        super(TimesheetForm, self).__init__(*args, **kwargs)

        TimesheetFieldClass = TIMESHEET_FIELD_CLASS_FOR_INPUT_METHOD[settings.TIMESHEET_INPUT_METHOD]
        for mission in missions:
            for day in days:
                key = "charge_%s_%s" % (mission.id, day.day)
                self.fields[key] = TimesheetFieldClass(required=False)
                # Order tabindex by day
                if day.isoweekday() in (6, 7) or day in holiday_days:
                    tabIndex = 100000  # Skip week-end from tab path
                    # Color week ends in grey
                    self.fields[key].widget.attrs.setdefault("style", "background-color: LightGrey;")
                else:
                    tabIndex = day.day
                self.fields[key].widget.attrs.setdefault("tabindex", tabIndex)

                if day == days[0]:  # Only show label for first day
                    tooltip = _("mission id: %s") % mission.mission_id()
                    self.fields[key].label = mark_safe("<span class='pydici-tooltip' title='%s'>%s</span>" % (tooltip, unicode(mission)))
                else:
                    self.fields[key].label = ""
            # Add staffing total and forecast in hidden field
            hwidget = forms.HiddenInput()
            # Mission id is added to ensure field key is uniq.
            key = "%s %s %s" % (timesheetTotal.get(mission.id, 0), mission.id, forecastTotal[mission.id])
            self.fields[key] = forms.CharField(widget=hwidget, required=False)

        # Add lunch ticket line
        if showLunchTickets:
            for day in days:
                key = "lunch_ticket_%s" % day.day
                self.fields[key] = forms.BooleanField(required=False)
                self.fields[key].widget.attrs.setdefault("size", 1)  # Reduce default size
                self.fields[key].widget.attrs.setdefault("data-role", "none")  # Don't apply jquery theme
                if day == days[0]:  # Only show label for first day
                    self.fields[key].label = _("Days without lunch ticket")
                else:
                    self.fields[key].label = ""  # Squash label
            # extra space is important - it is for forecast total (which does not exist for ticket...)
            key = "%s total-ticket " % timesheetTotal.get("ticket", 0)
            self.fields[key] = forms.CharField(widget=forms.HiddenInput(), required=False)


class MissionForm(PydiciCrispyModelForm):
    """Form used to change mission name and price"""
    contacts = MissionContactMChoices(required=False)
    lead = LeadChoices(required=False)
    responsible = ConsultantChoices(required=False, label=_("Responsible"),)

    def __init__(self, *args, **kwargs):
        super(MissionForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(Div(Column(Field("description", placeholder=_("Name of this mission. Leave blank when leads has only one mission")),
                                               AppendedText("price", "k€"), "billing_mode", "nature", "probability", "probability_auto", "active", css_class="col-md-6"),
                                        Column(Field("deal_id", placeholder=_("Leave blank to auto generate")), "subsidiary", "responsible", "contacts",
                                               css_class="col-md-6"),
                                        css_class="row"),
                                    Field("lead", type="hidden"), Field("archived_date", type="hidden"),
                                    self.submit)

    def clean_price(self):
        """Ensure mission price don't exceed remaining lead amount"""
        if not self.cleaned_data["price"]:
            # Don't check anything if not price given
            return self.cleaned_data["price"]

        if not self.instance.lead:
            raise ValidationError(_("Cannot add price to mission without lead"))

        if not self.instance.lead.sales:
            raise ValidationError(_("Mission's lead has no sales price. Define lead sales price."))

        total = 0  # Total price for all missions except current one
        for mission in self.instance.lead.mission_set.exclude(id=self.instance.id):
            if mission.price:
                total += mission.price

        remaining = self.instance.lead.sales - total
        if self.cleaned_data["price"] > remaining:
            raise ValidationError(_(u"Only %s k€ are remaining on this lead. Define a lower price" % remaining))

        # No error, we return data as is
        return self.cleaned_data["price"]

    class Meta:
        model = Mission
        fields = "__all__"


class FinancialConditionAdminForm(forms.ModelForm):
    """Form used to validate financial condition bought price field in admin"""
    class Meta:
        model = FinancialCondition
        fields = "__all__"

    def clean_bought_daily_rate(self):
        """Ensure bought daily rate is defined only for subcontractor"""
        if self.instance.consultant.subcontractor:
            if self.cleaned_data["bought_daily_rate"]:
                if 0 < self.cleaned_data["bought_daily_rate"] < self.cleaned_data["daily_rate"]:
                    return self.cleaned_data["bought_daily_rate"]
                else:
                    raise ValidationError(_("Bought daily rate must be positive and lower than daily rate"))
            else:
                raise ValidationError(_("Bought daily rate must be defined for subcontractor"))
        else:
            if self.cleaned_data["bought_daily_rate"]:
                raise ValidationError(_("Bought daily rate must be only be defined for subcontractor"))
            else:
                return self.cleaned_data["bought_daily_rate"]


class MissionContactsForm(forms.ModelForm):
    contacts = MissionContactMChoices(required=False, label=_("Add existing contacts"))

    class Meta:
        model = Mission
        fields = ["contacts", ]


class CycleTimesheetField(forms.ChoiceField):
    widget = forms.widgets.TextInput
    TS_VALUES = {u"0": None,
                 u"¼": "0.25",
                 u"½": "0.5",
                 u"¾": "0.75",
                 u"1": "1"}
    TS_VALUES_R = {0: "",
                   0.25: u"¼",
                   0.5: u"½",
                   0.75: u"¾",
                   1: u"1"}

    def __init__(self, choices=(), required=True, widget=None, label=None,
                 initial=None, help_text=None, *args, **kwargs):
        super(CycleTimesheetField, self).__init__(required=required, widget=widget, label=label,
                                             initial=initial, help_text=help_text, *args, **kwargs)
        self.choices = self.TS_VALUES.items()
        self.widget.attrs.setdefault("size", 1)  # Reduce default size
        self.widget.attrs.setdefault("readonly", 1)  # Avoid direct input for mobile
        self.widget.attrs.setdefault("class", "timesheet-cycle")

    def prepare_value(self, value):
        return self.TS_VALUES_R.get(value, None)

    def validate(self, value):
        if value in self.TS_VALUES.keys():
            return True

    def to_python(self, value):
        if not value and not self.required:
            return None
        if value is None or value == u"0":
            return None
        try:
            return Decimal(self.TS_VALUES.get(value))
        except KeyError:
            raise forms.ValidationError("Please enter a valid input (%s)." %
                                        ", ".join(self.TS_VALUES.keys()))


class KeyboardTimesheetField(forms.Field):
    def __init__(self, *args, **kwargs):
        kwargs['widget'] = forms.TextInput()
        super(KeyboardTimesheetField, self).__init__(*args, **kwargs)
        self.widget.attrs.setdefault("class", "timesheet-keyboard")

    def prepare_value(self, day_percent):
        if isinstance(day_percent, types.StringTypes):
            # day_percent may already be a string if prepare_value() is called
            # with the final value
            return day_percent
        return time_string_for_day_percent(day_percent)

    def to_python(self, value):
        if not value and not self.required:
            return 0
        try:
            return day_percent_for_time_string(value)
        except ValueError:
            raise forms.ValidationError('Invalid time string {}'.format(value))


TIMESHEET_FIELD_CLASS_FOR_INPUT_METHOD = {
    'cycle': CycleTimesheetField,
    'keyboard': KeyboardTimesheetField
}
