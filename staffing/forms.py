# coding:utf-8
"""
Staffing form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import timedelta, date
from decimal import Decimal

from django import forms
from django.forms.models import BaseInlineFormSet
from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError

from ajax_select.fields import AutoCompleteSelectField, AutoCompleteSelectMultipleField

from staffing.models import Mission, FinancialCondition


class ConsultantStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields"""
    def get_queryset(self):
        if not hasattr(self, '_queryset'):
            qs = super(ConsultantStaffingInlineFormset, self).get_queryset()
            if date.today().day > 5:
                lowerDayBound = date.today().replace(day=1)
            else:
                lastDayOfPreviousMonth = date.today().replace(day=1) + timedelta(-1)
                lowerDayBound = lastDayOfPreviousMonth.replace(day=1)

            qs = qs.filter(mission__active=True,  # Remove archived mission
                           staffing_date__gte=lowerDayBound)  # Remove past missions

            self._queryset = qs
        return self._queryset

    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(ConsultantStaffingInlineFormset, self).add_fields(form, index)
        form.fields["mission"] = AutoCompleteSelectField('mission', required=True, label=_("Mission"), show_help_text=False)
        form.fields["mission"].widget.attrs.setdefault("size", 8)  # Reduce default size
        form.fields["staffing_date"].widget.attrs.setdefault("size", 10)  # Reduce default size
        form.fields["charge"].widget.attrs.setdefault("size", 3)  # Reduce default size


class MissionStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields"""
    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(MissionStaffingInlineFormset, self).add_fields(form, index)
        form.fields["consultant"] = AutoCompleteSelectField('consultant', required=True, label=_("Consultant"), show_help_text=False)
        form.fields["consultant"].widget.attrs.setdefault("size", 8)  # Reduce default size
        form.fields["staffing_date"].widget.attrs.setdefault("size", 10)  # Reduce default size
        form.fields["charge"].widget.attrs.setdefault("size", 3)  # Reduce default size


class MassStaffingForm(forms.Form):
    """Massive staffing input forms that allow to define same staffing
    for a group of consultant accross different months"""
    def __init__(self, *args, **kwargs):
        staffing_dates = kwargs.pop("staffing_dates", [])
        super(MassStaffingForm, self).__init__(*args, **kwargs)

        self.fields["missions"] = AutoCompleteSelectMultipleField('mission', required=True, label=_("Missions"), show_help_text=False)
        self.fields["consultants"] = AutoCompleteSelectMultipleField('consultant', required=False, label=_("Consultants"), show_help_text=False)
        self.fields["charge"] = forms.fields.FloatField(label=_("Charge"), min_value=0.25, max_value=31)
        self.fields["comment"] = forms.fields.CharField(label=_("Comment"), max_length=100, required=False)
        self.fields["all_consultants"] = forms.fields.BooleanField(label=_("All active consultants"), required=False)
        self.fields["staffing_dates"] = forms.fields.MultipleChoiceField(label=_("Staffing dates"), choices=staffing_dates)


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

        for mission in missions:
            for day in days:
                key = "charge_%s_%s" % (mission.id, day.day)
                self.fields[key] = TimesheetField(required=False)
                self.fields[key].widget.attrs.setdefault("size", 1)  # Reduce default size
                self.fields[key].widget.attrs.setdefault("readonly", 1)  # Avoid direct input for mobile
                # Order tabindex by day
                if day.isoweekday() in (6, 7) or day in holiday_days:
                    tabIndex = 100000  # Skip week-end from tab path
                    # Color week ends in grey
                    self.fields[key].widget.attrs.setdefault("style", "background-color: LightGrey;")
                else:
                    tabIndex = day.day
                self.fields[key].widget.attrs.setdefault("tabindex", tabIndex)

                if day == days[0]:  # Only show label for first day
                    self.fields[key].label = unicode(mission)
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


class MissionAdminForm(forms.ModelForm):
    """Form used to validate mission price field in admin"""

    contacts = AutoCompleteSelectMultipleField('mission_contact', required=False, label=_("Contacts"), show_help_text=False)

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


class FinancialConditionAdminForm(forms.ModelForm):
    """Form used to validate financial condition bought price field in admin"""
    class Meta:
        model = FinancialCondition

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


class MissionContactForm(forms.ModelForm):
    contacts = AutoCompleteSelectMultipleField('mission_contact', required=False, label=_("New contacts"), show_help_text=False, help_text="")

    class Meta:
        model = Mission
        fields = ["contacts", ]


class TimesheetField(forms.ChoiceField):
    widget = forms.widgets.TextInput
    TS_VALUES = {u"0": None,
                u"¼": "0.25",
                u"½": "0.5",
                u"¾": "0.75",
                u"1": "1"
                }
    TS_VALUES_R = {0: "",
                   0.25: u"¼",
                   0.5: u"½",
                   0.75: u"¾",
                   1: u"1"}

    def __init__(self, choices=(), required=True, widget=None, label=None,
                 initial=None, help_text=None, *args, **kwargs):
        super(TimesheetField, self).__init__(required=required, widget=widget, label=label,
                                        initial=initial, help_text=help_text, *args, **kwargs)
        self.choices = self.TS_VALUES.items()

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
