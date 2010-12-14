# coding: utf-8
"""
Database access layer for pydici staffing module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.db import models
from django.db.models import Q
from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.db.models.signals import post_save
from django.contrib.admin.models import LogEntry, User, CHANGE
from django.contrib.contenttypes.models import ContentType

from datetime import datetime

from pydici.leads.models import Lead
from pydici.people.models import Consultant


class Mission(models.Model):
    MISSION_NATURE = (
            ('PROD', _("Productive")),
            ('NONPROD', _("Unproductive")),
            ('HOLIDAYS', _("Holidays")))
    PROBABILITY = (
            (0, _("Null")),
            (25, _("Low")),
            (50, _("Normal")),
            (75, _("High")),
            (100, _("Certain")))
    lead = models.ForeignKey(Lead, null=True, blank=True, verbose_name=_("Lead"))
    deal_id = models.CharField(_("Deal id"), max_length=100, blank=True)
    description = models.CharField(_("Description"), max_length=30, blank=True, null=True)
    nature = models.CharField(_("Type"), max_length=30, choices=MISSION_NATURE, default="PROD")
    active = models.BooleanField(_("Active"), default=True)
    probability = models.IntegerField(_("Proba"), default=50, choices=PROBABILITY)
    price = models.DecimalField(_(u"Price (k€)"), blank=True, null=True, max_digits=10, decimal_places=3)
    update_date = models.DateTimeField(_("Updated"), auto_now=True)

    def __unicode__(self):
        if self.description and not self.lead:
            return unicode(self.description)
        else:
            # As lead name computation generate lots of sql request, cache it to avoid
            # perf issue for screen that intensively use lead name (like consultant staffing)
            name = cache.get("missionName-%s" % self.id)
            if not name:
                name = unicode(self.lead)
                cache.set("missionName-%s" % self.id, name, 3)
            if self.description:
                return u"%s/%s" % (name, self.description)
            else:
                return name

    def full_name(self):
        """Full mission name with deal id if defined"""
        if self.deal_id:
            return u"%s (%s)" % (unicode(self), self.deal_id)
        else:
            return unicode(self)

    def no_more_staffing_since(self, refDate=datetime.now()):
        """@return: True if at least one staffing is defined after refDate. Zero charge staffing are considered."""
        return not bool(self.staffing_set.filter(staffing_date__gt=refDate).count())

    def staffed_consultant(self):
        """@return: sorted list of consultant forecasted for this mission"""
        consultants = set([s.consultant for s in self.staffing_set.all()])
        consultants = list(consultants)
        consultants.sort(cmp=lambda x, y: cmp(x.name, y.name))
        return consultants

    def create_default_staffing(self):
        """Initialize mission staffing based on lead hypothesis and current month"""
        now = datetime.now()
        now = now.replace(microsecond=0) # Remove useless microsecond that pollute form validation in callback
        for consultant in self.lead.staffing.all():
            staffing = Staffing()
            staffing.mission = self
            staffing.consultant = consultant
            staffing.staffing_date = now
            staffing.update_date = now
            staffing.last_user = "-"
            staffing.save()

    def sister_missions(self):
        """Return other missions linked to the same deal"""
        if self.lead:
            return self.lead.mission_set.exclude(id=self.id)
        else:
            return []

    def consultant_rates(self):
        """@return: dict with consultant as key and daily rate as value or 0 if not defined"""
        rates = {}
        for condition in FinancialCondition.objects.filter(mission=self):
            rates[condition.consultant] = condition.daily_rate
        # Put 0 for consultant forecasted on this mission but with daily rate
        for consultant in self.staffed_consultant():
            if not consultant in rates:
                rates[consultant] = 0
        return rates

    class Meta:
        ordering = ["nature", "lead__client__organisation__company", "description"]
        verbose_name = _("Mission")

class Holiday(models.Model):
    """List of public and enterprise specific holidays"""
    day = models.DateField(_("Date"))
    description = models.CharField(_("Description"), max_length=200)

    class Meta:
        verbose_name = _("Holiday")

class Staffing(models.Model):
    """The staffing fact forecasting table: charge per month per consultant per mission"""
    consultant = models.ForeignKey(Consultant)
    mission = models.ForeignKey(Mission, limit_choices_to=Q(active=True))
    staffing_date = models.DateField(_("Date"))
    charge = models.FloatField(_("Load"), default=0)
    comment = models.CharField(_("Comments"), max_length=500, blank=True, null=True)
    update_date = models.DateTimeField(blank=True, null=True)
    last_user = models.CharField(max_length=60, blank=True, null=True)

    def __unicode__(self):
        return "%s/%s (%s): %s" % (self.staffing_date.month, self.staffing_date.year, self.consultant.trigramme, self.charge)

    def save(self, force_insert=False, force_update=False):
        self.staffing_date = datetime(self.staffing_date.year, self.staffing_date.month, 1)
        super(Staffing, self).save(force_insert, force_update)

    class Meta:
        unique_together = (("consultant", "mission", "staffing_date"),)
        ordering = ["staffing_date", "consultant"]
        verbose_name = _("Staffing")

class Timesheet(models.Model):
    """The staffing table: charge per day per consultant per mission"""
    consultant = models.ForeignKey(Consultant)
    mission = models.ForeignKey(Mission, limit_choices_to=Q(active=True))
    working_date = models.DateField(_("Date"))
    charge = models.FloatField(_("Load"), default=0)

    def __unicode__(self):
        return "%s - %s: %s" % (self.working_date, self.consultant.trigramme, self.charge)

    class Meta:
        unique_together = (("consultant", "mission", "working_date"),)
        ordering = ["working_date", "consultant"]
        verbose_name = _("Timesheet")

class LunchTicket(models.Model):
    """Default is to give a lunck ticket every working day.
    Days without ticket (ie when lunch is paid by company) are tracked"""
    consultant = models.ForeignKey(Consultant)
    lunch_date = models.DateField(_("Date"))
    no_ticket = models.BooleanField(_("No lunch ticket"))

    class Meta:
        unique_together = (("consultant", "lunch_date"),)
        verbose_name = _("Lunch ticket")

class FinancialCondition(models.Model):
    """Mission financial condition"""
    consultant = models.ForeignKey(Consultant)
    mission = models.ForeignKey(Mission, limit_choices_to=Q(active=True))
    daily_rate = models.IntegerField(_("Daily rate"))

    class Meta:
        unique_together = (("consultant", "mission", "daily_rate"),)
        verbose_name = _("Financial condition")


# Signal definition
def updateLeadPrice(sender, **kwargs):
    """Called by mission update signal to update lead total price"""
    batch_username = "auto"
    mission = kwargs["instance"]
    price = 0
    try:
        user_id = user_id = User.objects.get(username=batch_username).id
    except User.DoesNotExist:
        # Create it
        user = User()
        user.username = batch_username
        user.save()
        user_id = user.id
    if mission.lead:
        for sisterMission in mission.lead.mission_set.all():
            if sisterMission.price:
                price += sisterMission.price
        mission.lead.sales = price
        mission.lead.save()
        # Log it
        LogEntry.objects.log_action(
                user_id=user_id,
                content_type_id=ContentType.objects.get_for_model(mission.lead).id,
                object_id=mission.lead.id,
                object_repr=unicode(mission.lead),
                change_message=ugettext("Price updated from mission"),
                action_flag=CHANGE)

# Connecting signals
post_save.connect(updateLeadPrice, sender=Mission)
