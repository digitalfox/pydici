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

from datetime import datetime, date

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
