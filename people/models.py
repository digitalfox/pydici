# coding: utf-8
"""
Database access layer for pydici people module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import F, Sum
from django.apps import apps
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.cache import cache

from datetime import date, timedelta

from core.utils import capitalize, cacheable, previousMonth, working_days
from crm.models import Subsidiary, Supplier
from people.tasks import compute_consultant_tasks


CONSULTANT_IS_IN_HOLIDAYS_CACHE_KEY = "Consultant.is_in_holidays%(id)s"
TIMESHEET_IS_UP_TO_DATE_CACHE_KEY = "Consultant.timesheet_is_up_to_date%(id)s"
CONSULTANT_TASKS_CACHE_KEY = "CONSULTANT_TASKS_%s"


class ConsultantProfile(models.Model):
    """Consultant hierarchy"""
    name = models.CharField(_("Name"), max_length=50, unique=True)
    level = models.IntegerField(_("Level"))

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["level"]
        verbose_name = _("Consultant profile")


class Consultant(models.Model):
    """A consultant that can manage a lead or be ressource of a mission"""
    name = models.CharField(max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)
    productive = models.BooleanField(_("Productive"), default=True)
    active = models.BooleanField(_("Active"), default=True)
    manager = models.ForeignKey("self", null=True, blank=True, related_name="team_as_manager", on_delete=models.SET_NULL)
    staffing_manager = models.ForeignKey("self", null=True, blank=True, related_name="team_as_staffing_manager", on_delete=models.SET_NULL)
    profil = models.ForeignKey(ConsultantProfile, verbose_name=_("Profil"), on_delete=models.CASCADE)
    subcontractor = models.BooleanField(_("Subcontractor"), default=False)
    subcontractor_company = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    telegram_alias = models.CharField(max_length=50, null=True, blank=True)
    telegram_id = models.BigIntegerField(null=True)

    def __str__(self):
        return self.name

    def full_name(self):
        return "%s (%s)" % (self.name, self.trigramme)

    def save(self, *args, **kwargs):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(Consultant, self).save(*args, **kwargs)

    def active_leads(self):
        """:return: active leads whose consultant is responsible for"""
        Lead = apps.get_model("leads", "Lead")  # Get Lead with get_model to avoid circular imports
        return Lead.objects.active().filter(responsible=self)

    def active_missions(self):
        """:return: consultant active missions based on forecast staffing"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        return Mission.objects.filter(active=True).filter(staffing__consultant=self).distinct().select_related("lead__client__organisation__company")

    def responsible_missions(self):
        """:return: consultant active missions whose he is responsible for"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        return Mission.objects.filter(active=True).filter(responsible=self).distinct().select_related("lead__client__organisation__company")

    def current_missions(self):
        """:return: active and responsible missions"""
        return self.active_missions() | self.responsible_missions()

    def forecasted_missions(self, month=None):
        """:return: consultant active missions on given month based on forecasted staffing
        If month is not defined, current month is used"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports

        if month:
            month = month.replace(day=1)
        else:
            month = date.today().replace(day=1)
        next_month = (month + timedelta(40)).replace(day=1)

        missions = Mission.objects.filter(active=True)
        missions = missions.filter(staffing__staffing_date__gte=month, staffing__staffing_date__lt=next_month, staffing__consultant=self)
        missions = missions.distinct()
        return missions

    def timesheet_missions(self, month=None):
        """Returns consultant missions on given month based on timesheet
        If month is not defined, current month is used"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        if month:
            month = month.replace(day=1)
        else:
            month = date.today().replace(day=1)
        nextMonth = (month + timedelta(40)).replace(day=1)
        missions = Mission.objects.filter(timesheet__working_date__gte=month, timesheet__working_date__lt=nextMonth, timesheet__consultant=self)
        missions = missions.distinct()
        return missions

    def get_financial_conditions(self, start_date, end_date):
        """Get consultant's financial condition between startDate (included) and enDate (excluded)
        @return: ((rate1, #days), (rate2, #days)...)"""
        from staffing.models import FinancialCondition
        fc = FinancialCondition.objects.filter(consultant=self,
                                               consultant__timesheet__charge__gt=0,  # exclude null charge
                                               consultant__timesheet__working_date__gte=start_date,
                                               consultant__timesheet__working_date__lt=end_date,
                                               consultant__timesheet=F("mission__timesheet"))  # Join to avoid duplicate entries
        fc = fc.values("daily_rate").annotate(Sum("consultant__timesheet__charge"))  # nb days at this rate group by timesheet
        fc = fc.values_list("daily_rate", "consultant__timesheet__charge__sum")
        fc = fc.order_by("daily_rate")
        return fc

    def get_rate_objective(self, working_date=None, rate_type="DAILY_RATE"):
        """Get the consultant rate objective for given date. rate_type can be DAILY_RATE (default) or PROD_RATE"""
        rate_types = dict(RateObjective.RATE_TYPE).keys()
        if rate_type not in rate_types:
            raise ValueError("rate_type must be one of %s" % ", ".join(rate_types))
        if not working_date:
            working_date = date.today()
        rates = self.rateobjective_set.filter(start_date__lte=working_date, rate_type=rate_type).order_by("-start_date")
        if rates:
            return rates[0]

    def get_production_rate(self, start_date, end_date):
        """Get consultant production rate between startDate (included) and enDate (excluded)"""
        Timesheet = apps.get_model("staffing", "Timesheet")
        timesheets = Timesheet.objects.filter(consultant=self,
                                              charge__gt=0,
                                              working_date__gte=start_date,
                                              working_date__lt=end_date)
        days = dict(timesheets.values_list("mission__nature").order_by("mission__nature").annotate(Sum("charge")))
        prod_days = days.get("PROD", 0)
        non_prod_days = days.get("NONPROD", 0)
        if (prod_days + non_prod_days) > 0:
            return prod_days / (prod_days + non_prod_days)
        else:
            return 0

    def get_turnover(self, start_date=None, end_date=None):
        """Get consultant turnover in euros of done missions according to timesheet and rates between startDate (included) and enDate (excluded). Only PROD missions are considered.
        Fixed price mission margin (profit or loss) are considered.
        @param start_date: if None, from the creation of earth
        @param end_date : if None, up to today
        @return: turnover in euros"""
        from staffing.models import Timesheet, FinancialCondition, Mission  # Late import to avoid circular reference
        if start_date is None:
            start_date = date(1977, 2, 18)
        if end_date is None:
            end_date = date.today()
        turnover = 0
        timesheets = Timesheet.objects.filter(consultant=self, working_date__gte=start_date, working_date__lt=end_date, mission__nature="PROD").order_by("mission__id")
        timesheets = timesheets.values_list("mission", "mission__billing_mode").annotate(Sum("charge"))
        rates = dict(FinancialCondition.objects.filter(consultant=self, mission__in=[i[0] for i in timesheets]).values_list("mission", "daily_rate"))
        for mission_id, billing_mode, charge in timesheets:
            mission_turnover = charge * rates.get(mission_id, 0)
            if billing_mode == "FIXED_PRICE":
                mission = Mission.objects.get(id=mission_id)
                done_work = mission.done_work_k()[1]
                price = float(mission.price or 0)
                if done_work and (done_work > price or (not mission.active and done_work < price)):
                    # mission is a fixed price and has been overshoot. Limit turnover to fixed price in proportion to what have been done
                    # or mission is archived and have margin
                    mission_turnover = mission_turnover * price / done_work
            turnover += mission_turnover

        return turnover

    @cacheable("Consultant.get_user%(id)s", 3600)
    def get_user(self):
        """Returns django user behind this consultant
        Current algorithm check only for equal trigramme
        First match is returned"""
        users = User.objects.filter(username__iexact=self.trigramme)
        if users.count() >= 1:
            return users[0]

    def team(self, exclude_self=True, only_active=False, staffing=False, subsidiary=False):
        """Returns Consultant team as a list of consultant. Default is directly managed team
        :param staffing: consider staffing manager instead of hierarchical manager
        :param subsidiary: take all subsidiary whomever is manager
        :param exclude_self:
        :param only_active:"""
        if subsidiary:
            team = Consultant.objects.filter(company=self.company)
        elif staffing:
            team = self.team_as_staffing_manager.all()
        else:
            team = self.team_as_manager.all()

        if exclude_self:
            team = team.exclude(id=self.id)
        if only_active:
            team = team.filter(active=True)
        return team

    def user_team(self, exclude_self=True, only_active=False, staffing=False, subsidiary=False):
        """Returns consultant team as list of pydici user"""
        users = [c.get_user() for c in self.team(exclude_self=exclude_self, only_active=only_active, staffing=staffing, subsidiary=subsidiary)]
        return [u for u in users if u is not None]

    def done_days(self):
        """Returns numbers of days worked up to today (according his timesheet) for current month"""
        from staffing.models import Timesheet  # Do that here to avoid circular imports
        today = date.today()

        days = Timesheet.objects.filter(consultant=self,
                                        charge__gt=0,
                                        working_date__gte=today.replace(day=1),
                                        working_date__lte=today).aggregate(Sum("charge"))
        days = list(days.values())[0]
        return days or 0

    def forecasted_days(self):
        """Forecasted days for current month without considering mission probability"""
        from staffing.models import Staffing  # Do that here to avoid circular imports
        today = date.today()

        days = Staffing.objects.filter(consultant=self,
                                       charge__gt=0,
                                       staffing_date__gte=today.replace(day=1),
                                       staffing_date__lte=today).aggregate(Sum("charge"))
        days = list(days.values())[0]
        return days or 0

    @cacheable(CONSULTANT_IS_IN_HOLIDAYS_CACHE_KEY, 6*3600)
    def is_in_holidays(self):
        """True if consultant is in holiday today. Else False"""
        Timesheet = apps.get_model("staffing", "Timesheet")  # Get Timesheet with get_model to avoid circular imports
        Holiday = apps.get_model("staffing", "Holiday")  # Idem
        working_date = date.today()
        holidays = Holiday.objects.filter(day__gte=working_date)
        day = timedelta(1)
        while working_date.weekday() in (5, 6) or working_date in holidays:
            # Go to next open day
            working_date += day

        if Timesheet.objects.filter(consultant=self, mission__nature="HOLIDAYS", working_date=working_date).count() > 0:
            return True
        else:
            return False

    def get_absolute_url(self):
        return reverse('people:consultant_home', args=[str(self.trigramme)])

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Consultant")

    @cacheable(TIMESHEET_IS_UP_TO_DATE_CACHE_KEY, 6 * 3600)
    def timesheet_is_up_to_date(self):
        """return tuple (previous month late days, current month late days). (0, 0) means everything is up to date. Current day is not included"""
        Timesheet = apps.get_model("staffing", "Timesheet")  # Get Timesheet with get_model to avoid circular imports
        from staffing.utils import holidayDays  # Idem
        result = []
        current_month = date.today().replace(day=1)
        for month, up_to in ((previousMonth(current_month), current_month), (current_month, date.today())):
            wd = working_days(month, holidayDays(month=month), upToToday=True)
            td = list(Timesheet.objects.filter(consultant=self, working_date__lt=up_to, working_date__gte=month).aggregate(Sum("charge")).values())[0] or 0
            result.append(wd - td)
        return result

    def get_tasks(self):
        """gather all tasks consultant should do
        :return: list of (task_name, count, link, priority(1-3))"""
        tasks = cache.get(CONSULTANT_TASKS_CACHE_KEY % self.id)
        if tasks is not None:
            return tasks
        else:
            # we should never have a cache miss on that on normal production mode. Just in case, compute it synchronously
            return compute_consultant_tasks(self.id)


class RateObjective(models.Model):
    """Consultant rates objective
    DAILY_RATE is the rate in € for each sold days
    PROD_RATE is the rate in % (int 0..100) on production days over all but holidays available days"""
    RATE_TYPE = (("DAILY_RATE", _("daily rate")),
                 ("PROD_RATE", _("production rate")))
    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE)
    start_date = models.DateField(_("Starting"))
    rate = models.IntegerField(_("Rate"), null=True)
    rate_type = models.CharField(_("Rate type"), max_length=30, choices=RATE_TYPE)


class SalesMan(models.Model):
    """A salesman"""
    name = models.CharField(_("Name"), max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)
    active = models.BooleanField(_("Active"), default=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)

    def __str__(self):
        return "%s (%s)" % (self.name, self.company)

    def save(self, *args, **kwargs):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(SalesMan, self).save(*args, **kwargs)

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Salesman")
        verbose_name_plural = _("Salesmen")
