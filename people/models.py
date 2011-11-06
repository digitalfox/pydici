# coding: utf-8
"""
Database access layer for pydici people module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.db.models import F, Sum
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from datetime import date, timedelta

from pydici.core.utils import capitalize
from pydici.core.models import Subsidiary
from pydici.actionset.models import ActionState
from pydici.actionset.utils import launchTrigger

class ConsultantProfile(models.Model):
    """Consultant hierarchy"""
    name = models.CharField(_("Name"), max_length=50, unique=True)
    level = models.IntegerField(_("Level"))

    def __unicode__(self): return self.name

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
    manager = models.ForeignKey("self", null=True, blank=True)
    profil = models.ForeignKey(ConsultantProfile, verbose_name=_("Profil"))
    subcontractor = models.BooleanField(_("Subcontractor"), default=False)
    subcontractor_company = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self): return self.name

    def full_name(self): return u"%s (%s)" % (self.name, self.trigramme)

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(Consultant, self).save(force_insert, force_update)

    def active_missions(self):
        """Returns consultant active missions based on forecast staffing"""
        # Get Mission class by introspecting FK instead of import to avoid circular imports
        Mission = self.staffing_set.model.mission.field.related.parent_model
        return Mission.objects.filter(active=True).filter(staffing__consultant=self).distinct()

    def forecasted_missions(self, month=None):
        """Returns consultant active missions on given month based on forecasted staffing
        If month is not defined, current month is used"""
        if month:
            month = month.replace(day=1)
        else:
            month = date.today().replace(day=1)
        nextMonth = (month + timedelta(40)).replace(day=1)
        # Get Mission class by introspecting FK instead of import to avoid circular imports
        Mission = self.staffing_set.model.mission.field.related.parent_model
        missions = Mission.objects.filter(active=True)
        missions = missions.filter(staffing__staffing_date__gte=month, staffing__staffing_date__lt=nextMonth, staffing__consultant=self)
        missions = missions.distinct()
        return missions

    def timesheet_missions(self, month=None):
        """Returns consultant missions on given month based on timesheet
        If month is not defined, current month is used"""
        if month:
            month = month.replace(day=1)
        else:
            month = date.today().replace(day=1)
        nextMonth = (month + timedelta(40)).replace(day=1)
        # Get Mission class by introspecting FK instead of import to avoid circular imports
        Mission = self.staffing_set.model.mission.field.related.parent_model
        missions = Mission.objects.filter(timesheet__working_date__gte=month, timesheet__working_date__lt=nextMonth, timesheet__consultant=self)
        missions = missions.distinct()
        return missions

    def getFinancialConditions(self, startDate, endDate):
        """Get consultant's financial condition between startDate (included) and enDate (excluded)
        @return: ((rate1, #days), (rate2, #days)...)"""
        from pydici.staffing.models import FinancialCondition
        fc = FinancialCondition.objects.filter(consultant=self,
                                               consultant__timesheet__charge__gt=0, # exclude null charge
                                               consultant__timesheet__working_date__gte=startDate,
                                               consultant__timesheet__working_date__lt=endDate,
                                               consultant__timesheet=F("mission__timesheet")) # Join to avoid duplicate entries
        fc = fc.values("daily_rate").annotate(Sum("consultant__timesheet__charge")) # nb days at this rate group by timesheet
        fc = fc.values_list("daily_rate", "consultant__timesheet__charge__sum")
        fc = fc.order_by("daily_rate")
        return fc

    def getUser(self):
        """Returns django user behind this consultant
        Current algorithm check only for equal trigramme
        First match is returned"""
        users = User.objects.filter(username__iexact=self.trigramme)
        if users.count() >= 1:
            return users[0]

    def team(self):
        """Returns Consultant team as a list of consultant"""
        return self.consultant_set.exclude(id=self.id)

    def userTeam(self):
        """Returns consultant team as list of pydici user"""
        return [c.getUser() for c in self.team()]

    def actions(self):
        """Returns pending actions"""
        return ActionState.objects.filter(user=self.getUser(), state="TO_BE_DONE")

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

    def __unicode__(self): return "%s (%s)" % (self.name, self.company)

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(SalesMan, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Salesman")
        verbose_name_plural = _("Salesmen")

# Signal handling to throw actionset
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
