    # coding:utf-8
"""
Staffing form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
import types

from datetime import timedelta, date, datetime
from decimal import Decimal
from math import sqrt

from django import forms
from django.conf import settings
from django.forms.models import BaseInlineFormSet
from django.forms import ChoiceField, ModelChoiceField, NumberInput
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.db.models import Sum


from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Column, Field, Row
from crispy_forms.bootstrap import AppendedText, TabHolder, Tab
from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget, Select2Widget
from django.utils import formats


from staffing.models import Mission, Staffing, MarketingProduct, Timesheet
from people.models import Consultant
from core.forms import PydiciCrispyModelForm, PydiciSelect2WidgetMixin
from people.forms import ConsultantChoices, ConsultantMChoices
from crm.forms import MissionContactMChoices
from staffing.utils import staffingDates, time_string_for_day_percent, day_percent_for_time_string
from staffing.optim import OPTIM_NEWBIE_SENIOR_LIMIT, OPTIM_SENIOR_DIRECTOR_LIMIT, OPTIM_NEWBIE_LIMIT
from core.utils import nextMonth


class MissionChoices(PydiciSelect2WidgetMixin, ModelSelect2Widget):
    model = Mission.objects
    search_fields = ["deal_id__icontains", "description__icontains", "lead__name__icontains", "lead__deal_id__icontains",
                     "lead__client__organisation__name__icontains", "lead__client__organisation__company__name__icontains"]

    def get_queryset(self):
        return self.queryset or Mission.objects.filter(active=True)


class MissionMChoices(PydiciSelect2WidgetMixin, ModelSelect2MultipleWidget):
    model = Mission
    search_fields = MissionChoices.search_fields

    def get_queryset(self):
        return Mission.objects.filter(active=True)


class MarketingProductChoices(PydiciSelect2WidgetMixin, ModelSelect2Widget):
    model = MarketingProduct
    search_fields = ["code__icontains", "description__icontains"]

    def __init__(self, *args, **kwargs):
        self.mission = kwargs.pop("mission", None)
        super(MarketingProductChoices, self).__init__(*args, **kwargs)

    def get_queryset(self):
        if self.mission.nature == "PROD":
            return MarketingProduct.objects.filter(active=True, subsidiary=self.mission.subsidiary)
        else:
            return MarketingProduct.objects.none()


class LeadMissionChoices(PydiciSelect2WidgetMixin, ModelSelect2Widget):
    model = Mission
    search_fields = MissionChoices.search_fields

    def __init__(self, *args, **kwargs):
        self.lead = kwargs.pop("lead", None)
        super(LeadMissionChoices, self).__init__(*args, **kwargs)

    def label_from_instance(self, mission):
        if mission.description:
            return "%s (%s)" % (mission.mission_id(), mission.description)
        else:
            return mission.mission_id()

    def get_queryset(self):
        if self.lead:
            return Mission.objects.filter(lead=self.lead)
        else:
            return Mission.objects.all()


class StaffingDateChoicesField(ChoiceField):
    widget = Select2Widget(attrs={'data-placeholder': _("Select a month...")})

    def __init__(self, *args, **kwargs):
        minDate = kwargs.pop("minDate", None)
        maxDate = kwargs.pop("maxDate", None)
        if minDate:
            missionDuration = (date.today() - minDate).days / 30
            numberOfMonth = 24 + missionDuration
        else:
            numberOfMonth = 24
        kwargs["choices"] = [(i, formats.date_format(i, format="YEAR_MONTH_FORMAT")) for i in staffingDates(format="datetime", n=numberOfMonth, minDate=minDate, maxDate=maxDate)]
        kwargs["choices"].insert(0, ("", ""))  # Add the empty choice for extra empty choices
        super(StaffingDateChoicesField, self).__init__(*args, **kwargs)

    def has_changed(self, initial, data):
        initial = str(initial) if initial is not None else ''
        return initial != data

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return self.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValidationError(_("Invalid date format"), code='invalid')

    def strptime(self, value, format):
        return datetime.strptime(value, format).date()


class ConsultantStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields"""

    lowerDayBound = None  # Bound of staffing used to hide past staffing

    def get_queryset(self):
        if not hasattr(self, '_queryset'):
            qs = super(ConsultantStaffingInlineFormset, self).get_queryset()
            lastDayOfPreviousMonth = date.today().replace(day=1) + timedelta(-1)
            self.lowerDayBound = lastDayOfPreviousMonth.replace(day=1)

            qs = qs.filter(mission__active=True,  # Remove archived mission
                           staffing_date__gte=self.lowerDayBound)  # Remove past missions

            self._queryset = qs
        return self._queryset

    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(ConsultantStaffingInlineFormset, self).add_fields(form, index)
        form.fields["mission"] = ModelChoiceField(widget=MissionChoices(attrs={'data-placeholder':_("Select a mission to add forecast...")}), queryset=Mission.objects)
        form.fields["staffing_date"] = StaffingDateChoicesField(minDate=self.lowerDayBound)
        form.fields["charge"].widget.attrs["class"] = "numberinput form-control"
        form.fields["comment"].widget.attrs["class"] = "d-none d-lg-table-cell form-control textinput"


class MissionStaffingInlineFormset(BaseInlineFormSet):
    """Custom inline formset used to override fields and filter on time window"""
    def __init__(self, *args, **kwargs):
        kwargs["queryset"] = Staffing.objects.filter(staffing_date__gte=date.today()-timedelta(365))
        super(MissionStaffingInlineFormset, self).__init__(*args, **kwargs)

    def add_fields(self, form, index):
        """that adds the field in, overwriting the previous default field"""
        super(MissionStaffingInlineFormset, self).add_fields(form, index)
        if self.instance.start_date:
            minDate = self.instance.start_date.replace(day=1)
        else:
            minDate = self.instance.staffing_start_date()
            if minDate:
                minDate = max(minDate, date.today() - timedelta(365))
                minDate = min(minDate, date.today())
            else:
                minDate = None
        if self.instance.end_date:
            maxDate = self.instance.end_date.replace(day=1)
        else:
            maxDate = None
        form.fields["consultant"] = ModelChoiceField(widget=ConsultantChoices(attrs={'data-placeholder':_("Select a consultant to add forecast...")}), queryset=Consultant.objects)
        form.fields["staffing_date"] = StaffingDateChoicesField(minDate=minDate, maxDate=maxDate)
        form.fields["charge"].widget.attrs["class"] = "numberinput form-control"
        form.fields["comment"].widget.attrs["class"] = "d-none d-lg-table-cell form-control textinput"


class StaffingForm(forms.ModelForm):
    """Just a single staffing. Used to add sanity checks"""
    def clean(self):
        consultant = self.cleaned_data.get("consultant")
        charge = self.cleaned_data.get("charge")
        mission = self.cleaned_data.get("mission")
        staffing_date = self.cleaned_data.get("staffing_date")

        if staffing_date and mission and mission.start_date:
            if staffing_date < mission.start_date.replace(day=1):
                self.add_error("staffing_date", _("Staffing below must be after %s") % mission.start_date)
        if staffing_date and mission and mission.end_date:
            if staffing_date > mission.end_date:
                self.add_error("staffing_date", _("Staffing below must be before %s") % mission.end_date)
        if mission and staffing_date and consultant and charge and mission.management_mode=="LIMITED_INDIVIDUAL":
            done = Timesheet.objects.filter(consultant=consultant, mission=mission,
                                            working_date__gte=staffing_date, working_date__lt=nextMonth(staffing_date))
            done = done.aggregate(Sum("charge"))["charge__sum"] or 0
            if charge < done:
                self.add_error("charge", _("You can't define a forecast lower than already done on timesheet (%s)") % done)


class MassStaffingForm(forms.Form):
    """Massive staffing input forms that allow to define same staffing
    for a group of consultant accross different months"""
    def __init__(self, *args, **kwargs):
        staffing_dates = kwargs.pop("staffing_dates", [])
        super(MassStaffingForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields["charge"] = forms.fields.FloatField(label=_("Charge"), min_value=0.25, max_value=31)
        self.fields["comment"] = forms.fields.CharField(label=_("Comment"), max_length=100, required=False)
        self.fields["all_consultants"] = forms.fields.BooleanField(label=_("All active consultants"), required=False)
        self.fields["staffing_dates"] = forms.fields.MultipleChoiceField(label=_("Staffing dates"), choices=staffing_dates)
        self.fields["missions"] = forms.ModelMultipleChoiceField(widget=MissionMChoices, queryset=Mission.objects.all())
        self.fields["consultants"] = forms.ModelMultipleChoiceField(widget=ConsultantMChoices, queryset=Consultant.objects.all(), required=False)
        submit = Submit("Submit", _("Save"))
        submit.field_classes = "btn btn-primary"
        self.helper.layout = Layout(Div(Column("missions", "consultants", "all_consultants", css_class='col-md-6'),
                                        Column("charge", "staffing_dates", "comment", css_class='col-md-6'),
                                        css_class='row'),
                                    submit)


class TimesheetForm(forms.Form):
    """Consultant timesheet form. Checks are done on view side because it required to save data on db"""
    def __init__(self, *args, **kwargs):
        days = kwargs.pop("days", None)
        missions = kwargs.pop("missions", None)
        forecastTotal = kwargs.pop("forecastTotal", [])
        timesheetTotal = kwargs.pop("timesheetTotal", [])
        holiday_days = kwargs.pop("holiday_days", [])
        showLunchTickets = kwargs.pop("showLunchTickets", True)
        warning = kwargs.pop("warning", None)
        timesheet_view = kwargs.pop("timesheet_view", None)
        super(TimesheetForm, self).__init__(*args, **kwargs)

        TimesheetFieldClass = TIMESHEET_FIELD_CLASS_FOR_INPUT_METHOD[settings.TIMESHEET_INPUT_METHOD]

        # Init the timesheet form builder cursor
        global_timesheet_cursor = [days]

        is_calendar_view = timesheet_view == 'calendar'

        # override the timesheet form builder cursor for calendar view
        if is_calendar_view:
            global_timesheet_cursor = []
            week = []
            # split the month in weeks for calendar view
            for idx, day in enumerate(days):
                week.append(day)
                if day.isoweekday() == 7:
                    global_timesheet_cursor.append(week)
                    week = []
            if week:
                global_timesheet_cursor.append(week)

        # warning array is based on the global number of days index
        warning_day_index = 0

        # build the timesheet form for al type of views
        for idxw, week_days in enumerate(global_timesheet_cursor):
            for idxm, mission in enumerate(missions):
                for idxd, day in enumerate(week_days):
                    key = "charge_%s_%s" % (mission.id, day.day)
                    self.fields[key] = TimesheetFieldClass(required=False)
                    self.fields[key].weekday = day.isoweekday()
                    # Order tabindex by day
                    if day.isoweekday() in (6, 7) or day in holiday_days:
                        tabIndex = 100000  # Skip week-end from tab path
                        # Color week ends in grey
                        self.fields[key].widget.attrs.setdefault("style", "background-color: LightGrey;")
                    else:
                        tabIndex = day.day
                    self.fields[key].widget.attrs.setdefault("tabindex", tabIndex)

                    key = "charge_%s_%s" % (mission.id, day.day)
                    # default label's empty
                    self.fields[key].label = ""
                    # Show "mission label" only needed for the first day
                    if idxd == 0:
                        tooltip = _("mission id: %s") % mission.mission_id()
                        mission_link = escape(mission)
                        if mission.lead_id:
                            mission_description = "<span class='highlight-mission-sub-label'>%s</span>" % mission.description if mission.description else ""
                            # default inline mission label
                            mission_label = "%s - %s %s" % (mission.lead.client.organisation, mission.lead.name, "/ %s" % mission_description if mission_description else "")

                            # override mission label for calendar view
                            if is_calendar_view:
                                mission_lead_name = "<span class='lead-sub-label'>%s</span>" % mission.lead.name
                                mission_sub_label =  "<div class='lead-mission-sub-label'>%s %s</div>" % (mission_lead_name, (" %s" % mission_description).strip())
                                mission_label = "<div class='mission-label'><div class='client-mission-label'>%s</div> %s</div>" % (mission.lead.client.organisation, mission_sub_label)
                            mission_link = "<a href='%s'>%s</a>" % (mission.get_absolute_url(), mission_label)
                        self.fields[key].label = mark_safe("<div class='pydici-tooltip' title='%s'>%s</div>" % (escape(tooltip), mission_link))

                        # table column headers displays day labels for all missions
                        if idxm == 0:
                            self.fields[key].days = []
                            for d in week_days:
                                self.fields[key].days.append(d)

                    # last week or day of month displays the timesheet footer
                    if idxd == len(week_days) - 1:
                        # Add staffing total and forecast in hidden field
                        hwidget = forms.HiddenInput()
                        # Mission id is added to ensure field key is uniq (as for the week for calendar view)
                        key = "%s %s %s %s" % (timesheetTotal.get(mission.id, 0), idxw, mission.id, forecastTotal[mission.id])
                        self.fields[key] = forms.CharField(widget=hwidget, required=False)
                        # simple way for the template to differentiate week days over weekend days
                        self.fields[key].weekday = day.isoweekday()

                        # After the last mission being computed
                        # add extra rows for lunch tickets and warnings
                        if idxm == len(missions)-1:
                            if showLunchTickets:
                                for lunch_day in week_days:
                                    key = "lunch_ticket_%s" % lunch_day.day
                                    self.fields[key] = forms.BooleanField(required=False)
                                    self.fields[key].weekday = lunch_day.isoweekday()
                                    self.fields[key].widget.attrs.setdefault("size", 1)  # Reduce default size
                                    self.fields[key].widget.attrs.setdefault("data-role", "none")  # Don't apply jquery theme
                                    if lunch_day == week_days[0]:  # Only show label for first day
                                        self.fields[key].label = _("Days without lunch ticket")
                                    else:
                                        self.fields[key].label = ""  # Squash label
                                # extra space is important - it is for forecast total (which does not exist for ticket...)
                                # add week id for uniqueness purpose in calendar view
                                key = "%s %s total-ticket " % (timesheetTotal.get("ticket", 0), idxw)
                                self.fields[key] = forms.CharField(widget=forms.HiddenInput(), required=False)
                                # simple way for the template to differentiate week days over weekend days
                                self.fields[key].weekday = day.isoweekday()

                            # add week id for uniqueness purpose in calendar view
                            key = "week_warning_%s " % idxw
                            self.fields[key] = forms.CharField(widget=forms.HiddenInput(), required=False)
                            self.fields[key].warning = []
                            for warning_week_day in week_days:
                                # simple way for the template to differentiate week days over weekend days
                                self.fields[key].warning.append({"value":warning[warning_day_index], "weekday": warning_week_day.isoweekday()})
                                warning_day_index += 1


class MissionForm(PydiciCrispyModelForm):
    """Form used to change mission name and price"""

    def __init__(self, *args, **kwargs):
        super(MissionForm, self).__init__(*args, **kwargs)
        self.fields["marketing_product"] = ModelChoiceField(widget=MarketingProductChoices(mission=self.instance),
                                                            queryset=MarketingProduct.objects.filter(subsidiary=self.instance.subsidiary),
                                                            required=False)
        self.helper.layout = Layout(TabHolder(Tab(_("Identification"),
                                                  Row(Column(Field("description", placeholder=_("Name of this mission. Leave blank when leads has only one mission")),
                                                             AppendedText("price", "k€"),
                                                             Field("client_deal_id", placeholder=_("Leave blank to use lead client deal id")),
                                                             "contacts",
                                                             css_class="col-md-6"),
                                                      Column("subsidiary", "responsible", "nature", "marketing_product",
                                                             css_class="col-md-6"),
                                                      )),
                                              Tab(_("Management"),
                                                  Row(Column("billing_mode",
                                                             Field("start_date", placeholder=_("Forbid forecast before this date"), css_class="datepicker"),
                                                             css_class="col-md-6"),
                                                      Column("management_mode",
                                                             Field("end_date", placeholder=_("Forbid forecast after this date"), css_class="datepicker"),
                                                             css_class="col-md-6"),
                                                      )),
                                              Tab(_("Advanced"),
                                                  Row(Column( Field("deal_id", placeholder=_("Leave blank to auto generate")),
                                                              "analytic_code", "min_charge_multiple_per_day",
                                                              css_class="col-md-6"),
                                                      Column("probability", "probability_auto", "always_displayed",
                                                             css_class="col-md-6")),
                                                  ),
                                              ),
                                    "active",
                                    self.submit)

    def add_fields(self, form, index):
        super(MissionForm, self).add_fields(form, index)

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
        if self.cleaned_data["price"] > remaining and self.instance.management_mode != "ELASTIC":
            raise ValidationError(_("Only %s k€ are remaining on this lead. Define a lower price" % remaining))

        # No error, we return data as is
        return self.cleaned_data["price"]

    def _clean_start_end_date(self, field):
        if self.cleaned_data.get("start_date") and self.cleaned_data.get("end_date"):
            if self.cleaned_data["start_date"] > self.cleaned_data["end_date"]:
                raise ValidationError(_("start date must be prior to en date"))
        return self.cleaned_data[field]

    def clean_start_date(self):
        if self.cleaned_data.get("start_date") and self.instance.staffing_start_date():
            if self.cleaned_data.get("start_date") > self.instance.staffing_start_date():
                raise ValidationError(_("start date must be before staffing start date (%s)") % self.instance.staffing_start_date())
        return self._clean_start_end_date("start_date")

    def clean_end_date(self):
        if self.cleaned_data.get("end_date") and self.instance.staffing_end_date():
            if self.cleaned_data.get("end_date") < self.instance.staffing_end_date():
                raise ValidationError(_("end date must be after staffing end date (%s)") % self.instance.staffing_end_date())
        return self._clean_start_end_date("end_date")

    def clean(self):
        if self.cleaned_data["management_mode"] == "ELASTIC" and self.cleaned_data["billing_mode"] == "FIXED_PRICE":
            raise ValidationError(_("Fixed price mission cannot be elastic by definition"))
        if self.cleaned_data["nature"] == "NONPROD" and not self.cleaned_data["analytic_code"]:
            raise ValidationError(_("Analytics code must be defined for non production missions"))
        if self.cleaned_data["marketing_product"]:
            print("coucou")
            if self.cleaned_data["marketing_product"].subsidiary != self.cleaned_data["subsidiary"]:
                raise ValidationError(_("Marketing product must be from same subsidiary"))
        return self.cleaned_data

    class Meta:
        model = Mission
        exclude = ['archived_date', 'lead']
        widgets = {"contacts": MissionContactMChoices,
                   "responsible": ConsultantChoices}


class MissionContactsForm(forms.ModelForm):
    """Form used to edit Missions contacts (in Mission "Contacts" tabs) """

    class Meta:
        model = Mission
        fields = ["contacts", ]
        widgets = { "contacts": MissionContactMChoices }


class CycleTimesheetField(forms.ChoiceField):
    widget = forms.widgets.TextInput
    # The font used to display timesheet symbols map them to number
    # ● -> 0
    # ◕ -> 6
    # ◑ -> 2
    # ◔ -> 5
    # ◌ -> 8
    TS_VALUES = {"8": None,
                 "5": "0.25",
                 "2": "0.5",
                 "6": "0.75",
                 "0": "1"}
    TS_VALUES_R = {0: "",
                   0.25: "5",
                   0.5: "2",
                   0.75: "6",
                   1: "0"}

    def __init__(self, required=True, widget=None, label=None,
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
        if value is None or value == "8":
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
        if isinstance(day_percent, str):
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


class MissionOptimiserForm(forms.Form):
    """Declaration of mission staffing to optimise. Part of a formset included in OptimiserForm"""
    def __init__(self, *args, **kwargs):
        self.staffing_dates = kwargs.pop("staffing_dates", [])
        super().__init__(*args, **kwargs)
        qs = Mission.objects.filter(nature="PROD", active=True)
        self.fields["mission"] = forms.ModelChoiceField(widget=MissionChoices(attrs={'data-placeholder': _("Select mission to plan")}, queryset=qs), queryset=qs)
        for month in self.staffing_dates:
            self.fields["charge_%s" % month[1]] = forms.IntegerField(required=False, label=month[1], widget=NumberInput(attrs={'size': '1'}))
        self.fields["predefined_assignment"] = forms.ModelMultipleChoiceField(label=_("Predefined assignment"),
                                                                              required=False, widget=ConsultantMChoices,
                                                                              queryset=Consultant.objects.filter(active=True))
        self.fields["exclusions"] = forms.ModelMultipleChoiceField(label=_("Exclusions"),
                                                                   required=False, widget=ConsultantMChoices,
                                                                   queryset=Consultant.objects.filter(active=True))

    def clean_mission(self):
        mission = self.cleaned_data.get("mission")
        if mission.remaining() <= 0:
            raise ValidationError(_("Mission has no budget remaining"))
        return mission

    def clean_predefined_assignment(self):
        """Ensure that there's enough budget to plan at least one day per predefined assignment"""
        mission = self.cleaned_data.get("mission")
        if mission:
            rates = mission.consultant_rates()
            min_price = 0
            for consultant in self.cleaned_data.get("predefined_assignment"):
                if consultant in rates:
                    min_price += rates[consultant][0]/1000
                else:  # use consultant budget rate or set to zero
                    rate_objective = consultant.get_rate_objective(rate_type="DAILY_RATE")
                    if rate_objective:
                        min_price += rate_objective.rate / 1000
                    else:
                        min_price = 0
            remaining = mission.remaining()
            if min_price > remaining:
                raise ValidationError(_("Remaining budget (%s k€) is too low for at least one day of each predefined consultant") % remaining)

        return self.cleaned_data.get("predefined_assignment")

    def clean(self):
        mission = self.cleaned_data.get("mission")
        if not mission:
            # Mission has been discarded by previous check, no need to check further
            return self.cleaned_data
        min_date = mission.start_date or date(2000, 1, 1)
        max_date = mission.end_date or date(2100, 1, 1)
        mission_staffing_dates = [i for i in self.staffing_dates if i[0] >= min_date and (i[0] < max_date)]
        if mission and mission_staffing_dates and sum(self.cleaned_data["charge_%s" % month[1]] or 0 for month in mission_staffing_dates) == 0:
            # Charge is not defined. Get it from staffing
            charge = Staffing.objects.filter(mission=mission, staffing_date__gte=mission_staffing_dates[0][0]).aggregate(Sum("charge"))["charge__sum"] or 0
            if charge > 0:
                for month in mission_staffing_dates:
                    c = Staffing.objects.filter(mission=mission, staffing_date=month[0]).aggregate(
                        Sum("charge"))["charge__sum"]
                    self.cleaned_data["charge_%s" % month[1]] = int(c or 0)  # Solver only work with integer
            elif mission.price:
                # No staffing defined... infer something from mission remaining
                remaining = mission.remaining()
                rates = [i[0] for i in mission.consultant_rates().values()]
                if remaining > 0 and rates:
                    avg_rate = (sum(rates) / len(rates) / 1000) or 1 # default to 1K€ per day
                    days = int(remaining / avg_rate)
                    duration = sqrt(days / 20) * 2  # Guess duration with square root of man.month charge as a max. Take the double for safety
                    for i, month in enumerate(mission_staffing_dates):
                        if i > duration or i > 7 or duration == 0:
                            # Stop planning after guessed duration of 8 month
                            break
                        self.cleaned_data["charge_%s" % month[1]] = int(days / duration)
        # Ensure user do not try to forecast outside mission window
        for m in [i for i in self.cleaned_data if i.startswith("charge_")]:
            if self.cleaned_data[m] is None or self.cleaned_data[m] == 0:
                continue  # no need to warn for no/zero day forecast
            if m[len("charge_"):] not in [i[1] for i in mission_staffing_dates]:
                raise ValidationError(_("You cannot forecast outside mission defined window (%(start)s - %(end)s)") % {"start": mission.start_date or "∞",
                                                                                                                       "end": mission.end_date or "∞"})

        return self.cleaned_data


class MissionOptimiserFormsetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_method = "post"
        self.template = "bootstrap5/table_inline_formset.html"
        self.form_tag = False


class OptimiserForm(forms.Form):
    """A form to select optimiser input data and parameters"""
    def __init__(self, *args, **kwargs):
        self.subsidiary = kwargs.pop("subsidiary", None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

        self.fields["consultants"] = forms.ModelMultipleChoiceField(widget=ConsultantMChoices, queryset=Consultant.objects.filter(active=True), required=False)
        self.fields["projections"] = forms.ChoiceField(label=_("staffing projection freetime"), choices=(("full", _("full")), ("balanced", _("balanced")), ("none", _("none"))), initial="balanced")
        self.fields["director_quota"] = forms.IntegerField(label=_("Director min. quota (%)"), initial=10, min_value=0, max_value=100)
        self.fields["senior_quota"] = forms.IntegerField(label=_("Senior min. quota (%)"), initial=20, min_value=0, max_value=100)
        self.fields["newbie_quota"] = forms.IntegerField(label=_("Newbie min. quota (%)"), initial=40, min_value=0, max_value=100)
        self.fields["planning_weight"] = forms.ChoiceField(label=_("Mission planning weight"), choices=((0, _("None")), (1, _("Standard")), (2, _("High"))), initial=1)
        self.fields["freetime_weight"] = forms.ChoiceField(label=_("Consultant free time weight"), choices=((0, _("None")), (1, _("Standard")), (2, _("High"))), initial=1)
        self.fields["people_per_mission_weight"] = forms.ChoiceField(label=_("People per mission weight"), choices=((0, _("None")), (1, _("Standard")), (2, _("High"))), initial=1)
        self.fields["mission_per_people_weight"] = forms.ChoiceField(label=_("Mission per people weight"), choices=((0, _("None")), (1, _("Standard")), (2, _("High"))), initial=1)
        self.helper.layout = Layout(Div(Column(Row(Column("director_quota", css_class="col-md-3"), Column("senior_quota", css_class="col-md-3"),
                                                   Column("newbie_quota", css_class="col-md-3"), Column("projections", css_class="col-md-3")),
                                               "consultants",  css_class="col-md-6"),
                                        Column(Row(Column("planning_weight", "people_per_mission_weight", css_class="col-md-6"),
                                                   Column("freetime_weight", "mission_per_people_weight", css_class="col-md-6")),
                                               css_class="col-md-6"),
                                        css_class='row'))

    def clean_consultants(self):
        if len(self.cleaned_data["consultants"]) < 1:
            # no consultant defined ? Let's populate with all active and productive people except subcontractor
            consultants = Consultant.objects.filter(productive=True, active=True, subcontractor=False)
            if self.subsidiary:
                consultants = consultants.filter(company=self.subsidiary)
            self.cleaned_data["consultants"] = consultants
        return self.cleaned_data["consultants"]

    def clean_director_quota(self):
        levels = [c.profil.level for c in self.cleaned_data["consultants"]]
        if self.cleaned_data.get("consultants") and self.cleaned_data["director_quota"] > 0:
            if max(levels) < OPTIM_SENIOR_DIRECTOR_LIMIT:
                raise ValidationError(_("%s %% director profile is required but no director has been selected") % self.cleaned_data["director_quota"])
        return self.cleaned_data["director_quota"]

    def clean_senior_quota(self):
        levels = [c.profil.level for c in self.cleaned_data["consultants"]]
        if self.cleaned_data.get("consultants") and self.cleaned_data["senior_quota"] > 0:
            if len([i for i in levels if OPTIM_NEWBIE_SENIOR_LIMIT < i < OPTIM_SENIOR_DIRECTOR_LIMIT]) == 0:
                raise ValidationError(_("%s %% senior profile is required but no senior consultant has been selected") % self.cleaned_data["senior_quota"])
        return self.cleaned_data["senior_quota"]

    def clean_newbie_quota(self):
        levels = [c.profil.level for c in self.cleaned_data["consultants"]]
        if self.cleaned_data.get("consultants") and self.cleaned_data["newbie_quota"] > 0:
            if min(levels) > OPTIM_NEWBIE_LIMIT:
                raise ValidationError(_("%s %% newbie profile is required but no newbie consultant has been selected") % self.cleaned_data["newbie_quota"])
        return self.cleaned_data["newbie_quota"]

    def clean(self):
        if self.cleaned_data.get("newbie_quota", 0) + self.cleaned_data.get("senior_quota", 0) + self.cleaned_data.get("director_quota", 0) > 100:
            raise ValidationError(_("Sum of profiles quotas cannot exceed 100%"))
        return self.cleaned_data
