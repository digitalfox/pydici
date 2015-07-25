# coding: utf-8
"""
Database access layer for pydici people module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.db.models import F, Sum
from django.apps import apps
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.urlresolvers import reverse

from datetime import date, timedelta

from core.utils import capitalize, disable_for_loaddata
from crm.models import Subsidiary
from actionset.models import ActionState
from actionset.utils import launchTrigger


class ConsultantProfile(models.Model):
    """Consultant hierarchy"""
    name = models.CharField(_("Name"), max_length=50, unique=True)
    level = models.IntegerField(_("Level"))

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ["level"]
        verbose_name = _("Consultant profile")


class Consultant(models.Model):
    """A consultant that can manage a lead or be ressource of a mission"""
    name = models.CharField(max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"))
    productive = models.BooleanField(_("Productive"), default=True)
    active = models.BooleanField(_("Active"), default=True)
    manager = models.ForeignKey("self", null=True, blank=True, related_name="team_as_manager")
    staffing_manager = models.ForeignKey("self", null=True, blank=True, related_name="team_as_staffing_manager")
    profil = models.ForeignKey(ConsultantProfile, verbose_name=_("Profil"))
    subcontractor = models.BooleanField(_("Subcontractor"), default=False)
    subcontractor_company = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        return self.name

    def full_name(self):
        return u"%s (%s)" % (self.name, self.trigramme)

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(Consultant, self).save(force_insert, force_update)

    def active_missions(self):
        """Returns consultant active missions based on forecast staffing"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports
        return Mission.objects.filter(active=True).filter(staffing__consultant=self).distinct()

    def forecasted_missions(self, month=None):
        """Returns consultant active missions on given month based on forecasted staffing
        If month is not defined, current month is used"""
        Mission = apps.get_model("staffing", "Mission")  # Get Mission with get_model to avoid circular imports

        if month:
            month = month.replace(day=1)
        else:
            month = date.today().replace(day=1)
        nextMonth = (month + timedelta(40)).replace(day=1)

        missions = Mission.objects.filter(active=True)
        missions = missions.filter(staffing__staffing_date__gte=month, staffing__staffing_date__lt=nextMonth, staffing__consultant=self)
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

    def getFinancialConditions(self, startDate, endDate):
        """Get consultant's financial condition between startDate (included) and enDate (excluded)
        @return: ((rate1, #days), (rate2, #days)...)"""
        from staffing.models import FinancialCondition
        fc = FinancialCondition.objects.filter(consultant=self,
                                               consultant__timesheet__charge__gt=0,  # exclude null charge
                                               consultant__timesheet__working_date__gte=startDate,
                                               consultant__timesheet__working_date__lt=endDate,
                                               consultant__timesheet=F("mission__timesheet"))  # Join to avoid duplicate entries
        fc = fc.values("daily_rate").annotate(Sum("consultant__timesheet__charge"))  # nb days at this rate group by timesheet
        fc = fc.values_list("daily_rate", "consultant__timesheet__charge__sum")
        fc = fc.order_by("daily_rate")
        return fc

    def getRateObjective(self, workingDate=None):
        if not workingDate:
            workingDate = date.today()
        rates = self.rateobjective_set.filter(start_date__lte=workingDate).order_by("-start_date")
        if rates:
            return rates[0]

    def getProductionRate(self, startDate, endDate):
        """Get consultant production rate between startDate (included) and enDate (excluded)"""
        Timesheet = apps.get_model("staffing", "Timesheet")
        timesheets = Timesheet.objects.filter(consultant=self,
                                              charge__gt=0,
                                              working_date__gte=startDate,
                                              working_date__lt=endDate)
        timesheets = timesheets.exclude(mission__nature="HOLIDAYS")
        timesheets = timesheets.values("mission__nature").order_by("mission__nature").annotate(Sum("charge"))
        prodDays = timesheets.filter(mission__nature="PROD")
        nonProdDays = timesheets.filter(mission__nature="NONPROD")
        prodDays = prodDays[0]["charge__sum"] if prodDays else 0
        nonProdDays = nonProdDays[0]["charge__sum"] if nonProdDays else 0
        if (prodDays + nonProdDays) > 0:
            return prodDays / (prodDays + nonProdDays)
        else:
            return 0

    def getTurnover(self, startDate=None, endDate=None):
        """Get consultant turnover in euros of done missions according to timesheet and rates between startDate (included) and enDate (excluded). Only PROD missions are considered.
        Fixed price mission margin (profit or loss) are not considered.
        @param startDate: if None, from the creation of earth
        @param endDate : if None, up to today
        @return: turnover in euros"""
        from staffing.models import Timesheet, FinancialCondition  # Late import to avoid circular reference
        if startDate is None:
            startDate = date(1977, 2, 18)
        if endDate is None:
            endDate = date.today()
        turnover = 0
        timesheets = Timesheet.objects.filter(consultant=self, working_date__gte=startDate, working_date__lt=endDate, mission__nature="PROD").order_by("mission__id")
        timesheets = timesheets.values_list("mission").annotate(Sum("charge"))
        rates = dict(FinancialCondition.objects.filter(consultant=self, mission__in=[i[0] for i in timesheets]).values_list("mission", "daily_rate"))
        for mission, charge in timesheets:
            turnover += charge * rates.get(mission, 0)
        return turnover

    def getUser(self):
        """Returns django user behind this consultant
        Current algorithm check only for equal trigramme
        First match is returned"""
        users = User.objects.filter(username__iexact=self.trigramme)
        if users.count() >= 1:
            return users[0]

    def team(self, excludeSelf=True, onlyActive=False, staffing=False):
        """Returns Consultant team as a list of consultant"""
        if staffing:
            team = self.team_as_staffing_manager.all()
        else:
            team = self.team_as_manager.all()
        if excludeSelf:
            team = team.exclude(id=self.id)
        if onlyActive:
            team = team.filter(active=True)
        return team

    def userTeam(self, excludeSelf=True, onlyActive=False):
        """Returns consultant team as list of pydici user"""
        return [c.getUser() for c in self.team(excludeSelf=excludeSelf, onlyActive=onlyActive)]

    def pending_actions(self):
        """Returns pending actions"""
        return ActionState.objects.filter(user=self.getUser(), state="TO_BE_DONE").select_related().prefetch_related("target")

    def done_days(self):
        """Returns numbers of days worked up to today (according his timesheet) for current month"""
        from staffing.models import Timesheet  # Do that here to avoid circular imports
        today = date.today()

        days = Timesheet.objects.filter(consultant=self,
                                        charge__gt=0,
                                        working_date__gte=today.replace(day=1),
                                        working_date__lte=today).aggregate(Sum("charge")).values()[0]
        return days or 0

    def forecasted_days(self):
        """Forecasted days for current month without considering mission probability"""
        from staffing.models import Staffing  # Do that here to avoid circular imports
        today = date.today()

        days = Staffing.objects.filter(consultant=self,
                                       charge__gt=0,
                                       staffing_date__gte=today.replace(day=1),
                                       staffing_date__lte=today).aggregate(Sum("charge")).values()[0]
        return days or 0

    def get_absolute_url(self):
        return reverse('people.views.consultant_home', args=[str(self.id)])

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Consultant")


class RateObjective(models.Model):
    """Consultant rate objective"""
    consultant = models.ForeignKey(Consultant)
    start_date = models.DateField(_("Starting"))
    daily_rate = models.IntegerField(_("Daily rate"))


class SalesMan(models.Model):
    """A salesman"""
    name = models.CharField(_("Name"), max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"))
    active = models.BooleanField(_("Active"), default=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.company)

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(SalesMan, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Salesman")
        verbose_name_plural = _("Salesmen")


# Signal handling to throw actionset
@disable_for_loaddata
def consultantSignalHandler(sender, **kwargs):
    """Signal handler for new consultant"""

    if  not kwargs.get("created", False):
        return

    consultant = kwargs["instance"]
    targetUser = None
    if consultant.manager:
        targetUser = consultant.manager.getUser()

    if not targetUser:
        # Default to admin
        targetUser = User.objects.filter(is_superuser=True)[0]

    launchTrigger("NEW_CONSULTANT", [targetUser, ], consultant)

# Signal connection to throw actionset
post_save.connect(consultantSignalHandler, sender=Consultant)
