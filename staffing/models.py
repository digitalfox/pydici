# coding: utf-8
"""
Database access layer for pydici staffing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db import models, connections
from django.db.models import Sum, Min
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.contrib.admin.models import ContentType
from django.urls import reverse

from datetime import datetime, date, timedelta

from leads.models import Lead
from people.models import Consultant
from crm.models import MissionContact, Subsidiary
from actionset.utils import launchTrigger
from actionset.models import ActionState
from core.utils import disable_for_loaddata, cacheable, convertDictKeyToDate, nextMonth


class Mission(models.Model):
    MISSION_NATURE = (
            ('PROD', ugettext("Productive")),
            ('NONPROD', ugettext("Unproductive")),
            ('HOLIDAYS', ugettext("Holidays")))
    PROBABILITY = (
            (0, ugettext("Null (0 %)")),
            (25, ugettext("Low (25 %)")),
            (50, ugettext("Normal (50 %)")),
            (75, ugettext("High (75 %)")),
            (100, ugettext("Certain (100 %)")))
    BILLING_MODES = (
            (('FIXED_PRICE'), ugettext("Fixed price")),
            (('TIME_SPENT'), ugettext("Time spent")))
    lead = models.ForeignKey(Lead, null=True, blank=True, verbose_name=_("Lead"), on_delete=models.CASCADE)
    deal_id = models.CharField(_("Mission id"), max_length=100, blank=True)
    description = models.CharField(_("Description"), max_length=30, blank=True, null=True)
    nature = models.CharField(_("Type"), max_length=30, choices=MISSION_NATURE, default="PROD")
    billing_mode = models.CharField(_("Billing mode"), max_length=30, choices=BILLING_MODES, null=True)
    active = models.BooleanField(_("Active"), default=True)
    probability = models.IntegerField(_("Proba"), default=50)
    probability_auto = models.BooleanField(_("Automatic probability"), default=True)
    price = models.DecimalField(_(u"Price (k€)"), blank=True, null=True, max_digits=10, decimal_places=3)
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    contacts = models.ManyToManyField(MissionContact, blank=True)
    subsidiary = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)
    archived_date = models.DateTimeField(_("Archived date"), blank=True, null=True)
    responsible = models.ForeignKey(Consultant, related_name="%(class)s_responsible", verbose_name=_("Responsible"), blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        if self.description and not self.lead:
            return str(self.description)
        else:
            name = str(self.lead)
            if self.description:
                return u"%s/%s" % (name, self.description)
            else:
                return name

    def short_name(self):
        """Name with deal name, mission desc and id. No client name"""
        if self.lead:
            if self.description:
                return u"%s/%s (%s)" % (self.lead.name, self.description, self.mission_id())
            else:
                return u"%s (%s)" % (self.lead.name, self.mission_id())
        else:
            # default to full name
            return self.full_name()

    def full_name(self):
        """Full mission name with deal id"""
        return u"%s (%s)" % (str(self), self.mission_id())

    def no_more_staffing_since(self, refDate=None):
        """@return: True if at least one staffing is defined after refDate. Zero charge staffing are considered."""
        if not refDate:
            refDate = datetime.now().replace(day=1)  # Current month
        return not bool(self.staffing_set.filter(staffing_date__gte=refDate).count())

    def no_staffing_update_since(self, days=30):
        """@return: True if no staffing have been updated since 'days' number of days"""
        return not bool(self.staffing_set.filter(update_date__gte=(date.today() - timedelta(days))).count())

    def consultants(self):
        """@return: sorted list of consultants forecasted or that once charge timesheet for this mission"""
        # Do two distinct query and then gather data. It is much much more faster than the left outer join on the two tables in the same query.
        consultantsIdsFromStaffing = Consultant.objects.filter(staffing__mission=self).values_list("id", flat=True).distinct()
        consultantsIdsFromTimesheet = Consultant.objects.filter(timesheet__mission=self).values_list("id", flat=True).distinct()
        ids = set(list(consultantsIdsFromStaffing) + list(consultantsIdsFromTimesheet))
        return Consultant.objects.filter(id__in=ids).order_by("name")

    def create_default_staffing(self):
        """Initialize mission staffing based on lead hypothesis and current month"""
        today = date.today()
        if self.lead and self.lead.start_date and self.lead.start_date > today:
            staffing_date = self.lead.start_date
        else:
            staffing_date = today
        for consultant in self.lead.staffing.all():
            staffing = Staffing()
            staffing.mission = self
            staffing.consultant = consultant
            staffing.staffing_date = staffing_date
            staffing.update_date = datetime.now().replace(microsecond=0)  # Remove useless microsecond that pollute form validation in callback
            staffing.last_user = "-"
            staffing.save()

    def sister_missions(self):
        """Return other missions linked to the same deal"""
        if self.lead:
            return self.lead.mission_set.exclude(id=self.id)
        else:
            return []

    @cacheable("Mission.consultant_rates%(id)s", 5)
    def consultant_rates(self):
        """@return: dict with consultant as key and (daily rate, bought daily rate) as value or 0 if not defined."""
        rates = {}
        for condition in FinancialCondition.objects.filter(mission=self).select_related():
            rates[condition.consultant] = (condition.daily_rate, condition.bought_daily_rate)
        # Put 0 for consultant forecasted on this mission but without defined daily rate
        for consultant in self.consultants():
            if not consultant in rates:
                rates[consultant] = (0, 0)
        return rates

    def defined_rates(self):
        """@return: True if all rates are defined for consultants forecasted or that already consume time for this mission. Else False"""
        return not bool([i[0] for i in self.consultant_rates().values()].count(0))

    @cacheable("Mission.mission_id%(id)s", 120)
    def mission_id(self):
        """Compute mission id :
            if mission has lead, it is based on lead deal_id if exists
            else if mission deal_id is used or default to pk (id)"""
        if self.lead and self.lead.deal_id:
            rank = list(self.lead.mission_set.order_by("id")).index(self)  # compute mission rank
            return self.lead.deal_id + chr(97 + rank)  # chr(97) is 'a'
        elif self.deal_id:
            return self.deal_id
        else:
            return str(self.id)

    @cacheable("Mission.done_work%(id)s", 10)
    def done_work(self):
        """Compute done work according to timesheet for this mission
        Result is cached for few seconds
        @return: (done work in days, done work in euros)"""
        rates = dict([(i.id, j[0]) for i, j in self.consultant_rates().items()])  # switch to consultant id
        days = 0
        amount = 0
        timesheets = Timesheet.objects.filter(mission=self, working_date__lt=nextMonth(date.today()))
        timesheets = timesheets.values_list("consultant").annotate(Sum("charge")).order_by()
        for consultant_id, charge in timesheets:
            days += charge
            if consultant_id in rates:
                amount += charge * rates[consultant_id]
        return (days, amount)

    def done_work_k(self):
        """Same as done_work, but with amount in keur"""
        days, amount = self.done_work()
        return days, amount / 1000

    @cacheable("Mission.forecasted_work%(id)s", 10)
    def forecasted_work(self):
        """Compute forecasted work according to staffing for this mission
        Result is cached for few seconds
        @return: (forecasted work in days, forecasted work in euros"""
        rates = dict([(i.id, j[0]) for i, j in self.consultant_rates().items()])  # switch to consultant id
        days = 0
        amount = 0
        current_month = date.today().replace(day=1)
        staffings = Staffing.objects.filter(mission=self, staffing_date__gte=current_month)
        staffings = staffings.values_list("consultant").annotate(Sum("charge")).order_by()
        current_month_done = Timesheet.objects.filter(mission=self, working_date__gte=current_month, working_date__lt=nextMonth(date.today()))
        current_month_done = dict(current_month_done.values_list("consultant").annotate(Sum("charge")).order_by())
        for consultant_id, charge in staffings:
            days += charge  # Add forecasted days
            days -= current_month_done.get(consultant_id, 0) # Substract current month done works from forecastinng
            if consultant_id in rates:
                amount += charge * rates[consultant_id]
                amount -= current_month_done.get(consultant_id, 0) * rates[consultant_id]

        return (days, amount)

    def forecasted_work_k(self):
        """Same as forecasted_work, but with amount in keur"""
        days, amount = self.forecasted_work()
        return days, amount / 1000

    def margin(self, mode="current"):
        """Compute mission margin in keuros
        @:parameter mode: can be current (default) to compute margin as of today (ie. remaining budget) or target to compute margin at mission end (with forecasted work"""
        if self.price:
            done_days, done_amount = self.done_work_k()
            if mode=="current":
                return float(self.price) - done_amount
            else: # Target
                forecasted_days, forecasted_amount = self.forecasted_work_k()
                return float(self.price) - done_amount - forecasted_amount
        else:
            return 0

    def objectiveMargin(self, startDate=None, endDate=None):
        """Compute margin over rate objective
        @param startDate: starting date to consider. This date is included in range. If None, start date is the begining of the mission
        @param endDate: ending date to consider. This date is excluded from range. If None, end date is last timesheet for this mission.
        @return: dict where key is consultant, value is cumulated margin over objective"""
        dateTrunc = connections[Timesheet.objects.db].ops.date_trunc_sql  # Shortcut to SQL date trunc function
        result = {}
        consultant_rates = self.consultant_rates()
        # Gather timesheet (Only consider timesheet up to current month)
        timesheets = Timesheet.objects.filter(mission=self)
        if startDate:
            timesheets = timesheets.filter(working_date__gte=startDate)
        if endDate:
            timesheets = timesheets.filter(working_date__lt=endDate)
        timesheets = timesheets.order_by("working_date")
        timesheetMonths = list(timesheets.dates("working_date", "month"))
        for consultant in self.consultants():
            result[consultant] = 0  # Initialize margin over rate objective for this consultant
            data = dict(timesheets.filter(consultant=consultant).extra(select={'month': dateTrunc("month", "working_date")}).values_list("month").annotate(Sum("charge")).order_by("month"))
            data = convertDictKeyToDate(data)

            for month in timesheetMonths:
                n_days = data.get(month, 0)
                if consultant.subcontractor:
                    # Compute objective margin on sold rate
                    if consultant_rates[consultant][0] and consultant_rates[consultant][1]:
                        result[consultant] += n_days * (consultant_rates[consultant][0] - consultant_rates[consultant][1])
                else:
                    # Compute objective margin on rate objective for this period
                    objectiveRate = consultant.getRateObjective(workingDate=month, rate_type="DAILY_RATE")
                    if objectiveRate:
                        result[consultant] += n_days * (consultant_rates[consultant][0] - objectiveRate.rate)
        return result

    def actions(self):
        """Returns actions for this mission and its lead"""
        actionStates = ActionState.objects.filter(target_id=self.id,
                                                 target_type=ContentType.objects.get_for_model(self))
        if self.lead:
            actionStates = actionStates | ActionState.objects.filter(target_id=self.lead.id,
                                                                     target_type=ContentType.objects.get(app_label="leads", model="lead"))

        return actionStates.select_related()

    def pending_actions(self):
        """returns pending actions for this mission and its lead"""
        return self.actions().filter(state="TO_BE_DONE")

    def done_actions(self):
        """returns done actions for this mission and its lead"""
        return self.actions().exclude(state="TO_BE_DONE")

    @cacheable("Mission.staffing_start_date%(id)s", 10)
    def staffing_start_date(self):
        """Starting date (=oldiest) staffing date of this mission. None if no staffing"""
        start_dates = self.staffing_set.all().aggregate(Min("staffing_date")).values()
        if start_dates:
            return list(start_dates)[0]
        else:
            return None

    def pivotable_data(self, startDate=None, endDate=None):
        """Compute raw data for pivot table on that mission"""
        #TODO: factorize with staffing.views.mission_timesheet
        data = []
        mission_id = self.mission_id()
        mission_name = self.short_name()
        current_month = date.today().replace(day=1)  # Current month
        subsidiary = str(self.subsidiary)
        dateTrunc = connections[Timesheet.objects.db].ops.date_trunc_sql  # Shortcut to SQL date trunc function
        consultant_rates = self.consultant_rates()
        billing_mode = self.get_billing_mode_display()

        # Gather timesheet and staffing (Only consider data up to current month)
        timesheets = Timesheet.objects.filter(mission=self).filter(working_date__lt=nextMonth(current_month)).order_by("working_date")
        staffings = Staffing.objects.filter(mission=self).filter(staffing_date__lt=nextMonth(current_month)).order_by("staffing_date")
        if startDate:
            timesheets = timesheets.filter(working_date__gte=startDate)
            staffings = staffings.filter(staffing_date__gte=startDate)
        if endDate:
            timesheets = timesheets.filter(working_date__lte=endDate)
            staffings = staffings.filter(staffing_date__lte=endDate)
        timesheetMonths = list(timesheets.dates("working_date", "month"))
        staffingMonths = list(staffings.dates("staffing_date", "month"))

        for consultant in self.consultants():
            consultant_name = str(consultant)
            timesheet_data = dict(timesheets.filter(consultant=consultant).extra(select={'month': dateTrunc("month", "working_date")}).values_list("month").annotate(Sum("charge")).order_by("month"))
            timesheet_data = convertDictKeyToDate(timesheet_data)
            staffing_data = dict(staffings.filter(consultant=consultant).values_list("staffing_date").annotate(Sum("charge")).order_by("staffing_date"))
            staffing_data = convertDictKeyToDate(staffing_data)

            for month in set(timesheetMonths + staffingMonths):
                data.append({ugettext("mission id"): mission_id,
                             ugettext("mission name"): mission_name,
                             ugettext("consultant"): consultant_name,
                             ugettext("subsidiary"): subsidiary,
                             ugettext("billing mode"): billing_mode,
                             ugettext("date"): month.strftime("%Y/%m"),
                             ugettext("done (days)"): timesheet_data.get(month, 0),
                             ugettext("done (keur)"): timesheet_data.get(month, 0) * consultant_rates[consultant][0] / 1000,
                             ugettext("forecast (days)"): staffing_data.get(month, 0),
                             ugettext("forecast (keur)"): staffing_data.get(month, 0) * consultant_rates[consultant][0] / 1000})
        return data


    def get_absolute_url(self):
        return reverse('staffing:mission_home', args=[str(self.id)])

    class Meta:
        ordering = ["nature", "lead__client__organisation__company", "id", "description"]
        verbose_name = _("Mission")


class Holiday(models.Model):
    """List of public and enterprise specific holidays"""
    day = models.DateField(_("Date"))
    description = models.CharField(_("Description"), max_length=200)

    class Meta:
        verbose_name = _("Holiday")


class Staffing(models.Model):
    """The staffing fact forecasting table: charge per month per consultant per mission"""
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE)
    mission = models.ForeignKey(Mission, limit_choices_to={"active": True}, on_delete=models.CASCADE)
    staffing_date = models.DateField(_("Date"))
    charge = models.FloatField(_("Load"), default=0)
    comment = models.CharField(_("Comments"), max_length=500, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)
    last_user = models.CharField(max_length=60, blank=True, null=True)

    def __str__(self):
        return "%s/%s (%s): %s" % (self.staffing_date.month, self.staffing_date.year, self.consultant.trigramme, self.charge)

    def save(self, *args, **kwargs):
        self.staffing_date = datetime(self.staffing_date.year, self.staffing_date.month, 1)
        super(Staffing, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("people:consultant_home", args=[str(self.consultant.trigramme)]) + "#tab-staffing"

    class Meta:
        unique_together = (("consultant", "mission", "staffing_date"),)
        ordering = ["staffing_date", "consultant"]
        verbose_name = _("Staffing")


class Timesheet(models.Model):
    """The staffing table: charge per day per consultant per mission"""
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE)
    mission = models.ForeignKey(Mission, limit_choices_to={"active": True}, on_delete=models.CASCADE)
    working_date = models.DateField(_("Date"))
    charge = models.FloatField(_("Load"), default=0)

    def __str__(self):
        return "%s - %s: %s" % (self.working_date, self.consultant.trigramme, self.charge)

    class Meta:
        unique_together = (("consultant", "mission", "working_date"),)
        ordering = ["working_date", "consultant"]
        verbose_name = _("Timesheet")


class LunchTicket(models.Model):
    """Default is to give a lunck ticket every working day.
    Days without ticket (ie when lunch is paid by company) are tracked"""
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE)
    lunch_date = models.DateField(_("Date"))
    no_ticket = models.BooleanField(_("No lunch ticket"), default=True)

    class Meta:
        unique_together = (("consultant", "lunch_date"),)
        verbose_name = _("Lunch ticket")


class FinancialCondition(models.Model):
    """Mission financial condition"""
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE)
    mission = models.ForeignKey(Mission, limit_choices_to={"active": True}, on_delete=models.CASCADE)
    daily_rate = models.IntegerField(_("Daily rate"))
    bought_daily_rate = models.IntegerField(_("Bought daily rate"), null=True, blank=True)  # For subcontractor only

    class Meta:
        unique_together = (("consultant", "mission", "daily_rate"),)
        verbose_name = _("Financial condition")


# Signal handling to throw actionset
@disable_for_loaddata
def missionSignalHandler(sender, **kwargs):
    """Signal handler for new/updated missions"""
    mission = kwargs["instance"]
    targetUser = None
    if mission.lead and mission.lead.responsible:
        targetUser = mission.lead.responsible.getUser()
    else:
        # try to pick up one of staffee
        for consultant in mission.consultants():
            targetUser = consultant.getUser()
            if targetUser:
                break
    if not targetUser:
        # Default to admin
        targetUser = User.objects.filter(is_superuser=True)[0]

    if not mission.active:
        # Mission is archived. Remove all staffing
        if not mission.archived_date:
            mission.archived_date = datetime.now()
            mission.save()
            if mission.lead and mission.lead.state == "WON":
                launchTrigger("ARCHIVED_MISSION", [targetUser, ], mission)

        for staffing in mission.staffing_set.all():
            staffing.delete()
        if mission.lead:
            # If this was the last active mission of its client and not more active lead, flag client as inactive
            client = mission.lead.client
            if len(client.getActiveMissions()) == 0 and len(client.getActiveLeads().exclude(state="WON")) == 0:
                client.active = False
                client.save()
    # Handle actionset stuff :
    if not mission.nature == "PROD":
        # Don't throw actions for non prod missions
        return

    if  kwargs.get("created", False):
        launchTrigger("NEW_MISSION", [targetUser, ], mission)

# Signal connection to throw actionset
post_save.connect(missionSignalHandler, sender=Mission)
