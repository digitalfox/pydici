# coding: utf-8
"""
Database access layer for pydici staffing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db import models
from django.db.models import Sum, Min, Max, F, Q
from django.db.models.functions import TruncMonth
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext, pgettext
from django.urls import reverse

from auditlog.models import AuditlogHistoryField

from datetime import datetime, date, timedelta

from leads.models import Lead
from people.models import Consultant
from crm.models import MissionContact, Subsidiary
from core.utils import cacheable, nextMonth, get_parameter
from people.tasks import compute_consultant_tasks


class AnalyticCode(models.Model):
    code = models.CharField(max_length=100, unique=True)
    description = models.CharField(_("Description"), max_length=100, blank=True, null=True)

    def __str__(self):
        if self.description:
            return "%s (%s)" % (self.code, self.description)
        else:
            return self.code


class MarketingProduct(models.Model):
    code = models.CharField(max_length=100, unique=True)
    description = models.CharField(_("Description"), max_length=100, blank=True, null=True)
    subsidiary = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)
    active = models.BooleanField(_("Active"), default=True)

    def __str__(self):
        if self.description:
            return "%s (%s - %s)" % (self.code, self.description, self.subsidiary)
        else:
            return self.code

    class Meta:
        unique_together = [["code", "subsidiary"]]


class Mission(models.Model):
    MISSION_NATURE = (
            ('PROD',  gettext("Productive")),
            ('NONPROD',  gettext("Unproductive")),
            ('HOLIDAYS',  gettext("Holidays")))
    PROBABILITY = (
            (0,  gettext("Null (0 %)")),
            (25,  gettext("Low (25 %)")),
            (50,  gettext("Normal (50 %)")),
            (75,  gettext("High (75 %)")),
            (100,  gettext("Certain (100 %)")))
    BILLING_MODES = (
            ('FIXED_PRICE',  gettext("Fixed price")),
            ('TIME_SPENT',  gettext("Time spent")))
    MANAGEMENT_MODES = (
        ('LIMITED',  gettext("Limited")),
        ('LIMITED_INDIVIDUAL', gettext("Limited individual")),
        ('ELASTIC',  gettext("Elastic")),
        ('NONE', pgettext("masculine", "None")))
    lead = models.ForeignKey(Lead, null=True, blank=True, verbose_name=_("Lead"), on_delete=models.CASCADE)
    deal_id = models.CharField(_("Mission id"), max_length=100, blank=True)
    description = models.CharField(_("Description"), max_length=30, blank=True, null=True)
    nature = models.CharField(_("Type"), max_length=30, choices=MISSION_NATURE, default="PROD")
    billing_mode = models.CharField(_("Billing mode"), max_length=30, choices=BILLING_MODES, null=True)
    management_mode = models.CharField(_("Management mode"), max_length=30, choices=MANAGEMENT_MODES, default="NONE")
    active = models.BooleanField(_("Active"), default=True)
    probability = models.IntegerField(_("Proba"), default=50)
    probability_auto = models.BooleanField(_("Automatic probability"), default=True)
    price = models.DecimalField(_("Price (k€)"), blank=True, null=True, max_digits=10, decimal_places=3)
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    contacts = models.ManyToManyField(MissionContact, blank=True)
    subsidiary = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)
    archived_date = models.DateTimeField(_("Archived date"), blank=True, null=True)
    responsible = models.ForeignKey(Consultant, related_name="%(class)s_responsible", verbose_name=_("Responsible"), blank=True, null=True, on_delete=models.SET_NULL)
    analytic_code = models.ForeignKey(AnalyticCode, verbose_name=_("analytic code"), blank=True, null=True, on_delete=models.SET_NULL)
    marketing_product = models.ForeignKey(MarketingProduct, verbose_name=_("marketing product"), blank=True, null=True, on_delete=models.SET_NULL)
    start_date = models.DateField(_("Start date"), blank=True, null=True)
    end_date = models.DateField(_("End date"), blank=True, null=True)
    min_charge_multiple_per_day = models.FloatField(_("Min charge multiple per day"), default=0)
    client_deal_id = models.CharField(_("Client deal id"), max_length=100, blank=True)

    history = AuditlogHistoryField()

    def __str__(self):
        if self.description and not self.lead:
            return str(self.description)
        else:
            name = str(self.lead)
            if self.description:
                return "%s/%s" % (name, self.description)
            else:
                return name

    def save(self, *args, **kwargs):
        update_tasks = kwargs.pop("update_tasks", True)

        # inherit from lead client_deal_id if it has been defined after mission creation
        if self.lead and not self.client_deal_id:
            self.client_deal_id = self.lead.client_deal_id

        super(Mission, self).save(*args, **kwargs)

        if not self.active:
            # Mission is archived. Remove all staffing
            if not self.archived_date:
                self.archived_date = datetime.now()
                self.save()

            for staffing in self.staffing_set.all():
                staffing.delete()
            if self.lead:
                # If this was the last active mission of its client and not more active lead, flag client as inactive
                client = self.lead.client
                if len(client.getActiveMissions()) == 0 and len(client.getActiveLeads().exclude(state="WON")) == 0:
                    client.active = False
                    client.save()

        # update lead price if needed
        if self.lead and self.lead.sales:
            all_mission_price = self.lead.mission_set.aggregate(Sum("price"))["price__sum"] or 0
            if all_mission_price > self.lead.sales:
                self.lead.sales = all_mission_price
                self.lead.save()

        # update mission responsible tasks
        if self.responsible and update_tasks:
            compute_consultant_tasks.delay(self.responsible.id)

    def short_name(self):
        """Name with deal name, mission desc and id. No client name"""
        if self.lead:
            if self.description:
                return "%s/%s (%s)" % (self.lead.name, self.description, self.mission_id())
            else:
                return "%s (%s)" % (self.lead.name, self.mission_id())
        else:
            # default to full name
            return self.full_name()

    def full_name(self):
        """Full mission name with deal id"""
        return "%s (%s)" % (str(self), self.mission_id())

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
            if consultant not in rates:
                rates[consultant] = (0, 0)
        return rates

    def consultant_objective_rates(self):
        """:return: dict with consultant as key and list of starting date / objective rate on mission time span"""
        # TODO: add cache
        rates = {}
        # Get all consultants, with staffing, timesheet and even just financial conditions
        consultants = Consultant.objects.filter(financialcondition__mission=self).union(self.consultants())
        mission_timeframe = self.timesheet_set.aggregate(Min("working_date"), Max("working_date"))
        mission_timeframe.update(self.staffing_set.aggregate(Min("staffing_date"), Max("staffing_date")))
        try:
            start = min([i for i in [mission_timeframe["working_date__min"], mission_timeframe["staffing_date__min"]] if i is not None])
            end = max([i for i in [mission_timeframe["working_date__max"], mission_timeframe["staffing_date__max"]] if i is not None])
        except ValueError:  # Empty list
            start = date.today()
            end = date.today()
        current = start
        exit_condition = False
        while True:
            for consultant in consultants:
                if consultant not in rates:
                    rates[consultant] = []
                objective_rate = consultant.get_rate_objective(current, rate_type="DAILY_RATE")
                rates[consultant].append([current, objective_rate.rate if objective_rate else None])
            if exit_condition or current == end:
                break
            current += timedelta(366)  # guess what, some years have more than 365 days.
            if current > end:
                current = end
                exit_condition = True
        return rates

    def defined_rates(self):
        """:return: True if all rates are defined for consultants forecasted or that already consume time for this mission. Else False"""
        return set(self.consultants()).issubset(set(Consultant.objects.filter(financialcondition__mission=self)))

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

    def mission_analytic_code(self):
        """get analytic code of this mission. Mission id is used if not defined"""
        if self.analytic_code:
            return self.analytic_code.code
        else:
            return self.mission_id()

    @cacheable("Mission.done_work%(id)s", 10)
    def done_work(self):
        """Compute done work according to timesheet for this mission
        Result is cached for few seconds
        @return: (done work in days, done work in euros)"""
        return self.done_work_period(None, date.today())

    def done_work_k(self):
        """Same as done_work, but with amount in keur"""
        days, amount = self.done_work()
        return days, amount / 1000

    def done_work_period(self, start, end, include_internal_subcontractor=True,
                         include_external_subcontractor=True,
                         filter_on_subsidiary=None,
                         filter_on_consultant=None):
        """Compute done work according to timesheet for this mission
        @start: starting date (included)
        @end: ending date (excluded)
        @include_internal_subcontractor: to include (default) or not internal (other subsidiaries) consultants
        @include_external_subcontractor: to include (default) or not external subcontractor
        @filter_on_subsidiary: filter done work on consultant subsidiary. None (default) is all.
        @filter_on_consultant: filter done work only on given consultant. None (default) is all.
        @return: (done work in days, done work in euros)"""
        rates = dict([(i.id, j[0]) for i, j in self.consultant_rates().items()])  # switch to consultant id
        days = 0
        amount = 0
        timesheets = Timesheet.objects.filter(mission=self)
        if start:
            timesheets = timesheets.filter(working_date__gte=start)
        if end:
            timesheets = timesheets.filter(working_date__lt=end)
        if not include_external_subcontractor:
            timesheets = timesheets.filter(consultant__subcontractor=False)
        if not include_internal_subcontractor:
            timesheets = timesheets.filter(Q(consultant__company=F("mission__subsidiary")) | Q(consultant__subcontractor=True))
        if filter_on_subsidiary:
            timesheets = timesheets.filter(Q(consultant__company=filter_on_subsidiary) | Q(consultant__subcontractor=True))
        if filter_on_consultant:
            timesheets = timesheets.filter(consultant=filter_on_consultant)
        timesheets = timesheets.values_list("consultant").annotate(Sum("charge")).order_by()
        for consultant_id, charge in timesheets:
            days += charge
            if consultant_id in rates:
                amount += charge * rates[consultant_id]
        return days, amount

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
        current_month_done = Timesheet.objects.filter(mission=self, working_date__gte=current_month, working_date__lt=date.today())
        current_month_done = dict(current_month_done.values_list("consultant").annotate(Sum("charge")).order_by())
        current_month_staffing = Staffing.objects.filter(mission=self, staffing_date__gte=current_month, staffing_date__lt=nextMonth(current_month))
        current_month_staffing = dict(current_month_staffing.values_list("consultant").annotate(Sum("charge")).order_by())
        for consultant_id, charge in staffings:
            days += charge  # Add forecasted days
            current_month_balance = current_month_staffing.get(consultant_id, 0) - current_month_done.get(consultant_id, 0)
            if current_month_balance > 0:
                charge_adjustement = -current_month_done.get(consultant_id, 0)  # leave remaining forecast
            else:
                charge_adjustement = -current_month_staffing.get(consultant_id, 0) # forecast has been exhausted
            days += charge_adjustement
            if consultant_id in rates:
                amount += (charge + charge_adjustement) * rates[consultant_id]
        if days < 0:
            # Negative forecast, means no forecast.
            days = 0
            amount = 0
        return days, amount

    def forecasted_work_k(self):
        """Same as forecasted_work, but with amount in keur"""
        days, amount = self.forecasted_work()
        return days, amount / 1000

    def remaining(self, mode="current"):
        """Compute mission remaining, ie. unused budget, in keuros
        @:parameter mode: can be current (default) to compute remaining as of today or target to compute remaning at mission end (with forecasted work)"""
        if self.price:
            done_days, done_amount = self.done_work_k()
            if mode == "current":
                return float(self.price) - done_amount
            else: # Target
                forecasted_days, forecasted_amount = self.forecasted_work_k()
                return float(self.price) - done_amount - forecasted_amount
        else:
            return 0

    def target_remaining(self):
        return self.remaining(mode="target")

    def objectiveMargin(self, startDate=None, endDate=None):
        """Compute margin over rate objective
        @param startDate: starting date to consider. This date is included in range. If None, start date is the begining of the mission
        @param endDate: ending date to consider. This date is excluded from range. If None, end date is last timesheet for this mission.
        @return: dict where key is consultant, value is cumulated margin over objective"""
        result = {}
        consultant_rates = self.consultant_rates()
        # Gather timesheet and staffing (starting current month)
        timesheets = Timesheet.objects.filter(mission=self)
        staffings = Staffing.objects.filter(mission=self, staffing_date__gte=date.today().replace(day=1))
        if startDate:
            timesheets = timesheets.filter(working_date__gte=startDate)
            staffings = staffings.filter(staffing_date__gte=startDate)
        if endDate:
            timesheets = timesheets.filter(working_date__lt=endDate)
            staffings = staffings.filter(staffing_date__lt=endDate)
        timesheets = timesheets.order_by("working_date")
        staffings = staffings.order_by("staffing_date")
        timesheetMonths = list(timesheets.dates("working_date", "month"))
        staffingMonths = list(staffings.dates("staffing_date", "month"))
        for consultant in self.consultants():
            result[consultant] = 0  # Initialize margin over rate objective for this consultant
            timesheet_data = dict(timesheets.filter(consultant=consultant).annotate(month=TruncMonth("working_date")).values_list("month").annotate(Sum("charge")).order_by("month"))
            staffing_data = dict(staffings.filter(consultant=consultant).annotate(month=TruncMonth("staffing_date")).values_list("month").annotate(Sum("charge")).order_by("month"))

            for month in timesheetMonths:
                n_days = timesheet_data.get(month, 0)
                if consultant.subcontractor:
                    # Compute objective margin on sold rate after removing standard subcontractor budget margin
                    if consultant_rates[consultant][0] is not None and consultant_rates[consultant][1]:
                        result[consultant] += n_days * (consultant_rates[consultant][0] * (1 - get_parameter("SUBCONTRACTOR_BUDGET_MARGIN")/100) - consultant_rates[consultant][1])
                else:
                    # Compute objective margin on rate objective for this period
                    objectiveRate = consultant.get_rate_objective(working_date=month, rate_type="DAILY_RATE")
                    if objectiveRate:
                        result[consultant] += n_days * (consultant_rates[consultant][0] - objectiveRate.rate)

            for month in staffingMonths:
                n_days = staffing_data.get(month, 0) - timesheet_data.get(month, 0)  # substract timesheet data from staffing to avoid twice counting
                if consultant.subcontractor:
                    # Compute objective margin on sold rate
                    if consultant_rates[consultant][0] is not None and consultant_rates[consultant][1]:
                        result[consultant] += n_days * (consultant_rates[consultant][0] * (1 - get_parameter("SUBCONTRACTOR_BUDGET_MARGIN")/100) - consultant_rates[consultant][1])
                else:
                    # Compute objective margin on rate objective for this period
                    objectiveRate = consultant.get_rate_objective(working_date=month, rate_type="DAILY_RATE")
                    if objectiveRate:
                        result[consultant] += n_days * (consultant_rates[consultant][0] - objectiveRate.rate)
        return result

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
        #TODO: denormalize by adding done/planned as a type column and move days/amount in values columns
        data = []
        mission_id = self.mission_id()
        mission_name = self.short_name()
        current_month = date.today().replace(day=1)  # Current month
        subsidiary = str(self.subsidiary)
        consultant_rates = self.consultant_rates()
        billing_mode = self.get_billing_mode_display()
        marketing_product = self.marketing_product.description if self.marketing_product else gettext("undefined")

        # Gather timesheet and staffing (Only consider data up to current month)
        timesheets = Timesheet.objects.filter(mission=self).filter(working_date__lt=nextMonth(current_month)).order_by("working_date")
        staffings = Staffing.objects.filter(mission=self).filter(staffing_date__gte=nextMonth(current_month)).order_by("staffing_date")
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
            timesheet_data = dict(timesheets.filter(consultant=consultant).annotate(month=TruncMonth("working_date")).values_list("month").annotate(Sum("charge")).order_by("month"))
            staffing_data = dict(staffings.filter(consultant=consultant).values_list("staffing_date").annotate(Sum("charge")).order_by("staffing_date"))

            for month in set(timesheetMonths + staffingMonths):
                data.append({ gettext("mission id"): mission_id,
                              gettext("mission name"): mission_name,
                              gettext("marketing product"): marketing_product,
                              gettext("consultant"): consultant_name,
                              gettext("subsidiary"): subsidiary,
                              gettext("billing mode"): billing_mode,
                              gettext("date"): month.strftime("%Y/%m"),
                              gettext("done (days)"): timesheet_data.get(month, 0),
                              gettext("done (€)"): timesheet_data.get(month, 0) * consultant_rates[consultant][0],
                              gettext("forecast (days)"): staffing_data.get(month, 0),
                              gettext("forecast (€)"): staffing_data.get(month, 0) * consultant_rates[consultant][0]})
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
    staffing_date.db_index = True  # Because time is in third position on uniq index defined below
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
        ordering = ["staffing_date", "consultant", "-mission__nature",
                    "mission__lead__client__organisation__company__name", "mission__description", "id"]
        verbose_name = _("Staffing")


class Timesheet(models.Model):
    """The staffing table: charge per day per consultant per mission"""
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE)
    mission = models.ForeignKey(Mission, limit_choices_to={"active": True}, on_delete=models.CASCADE)
    working_date = models.DateField(_("Date"))
    working_date.db_index = True  # Because time is in third position on uniq index defined below
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
