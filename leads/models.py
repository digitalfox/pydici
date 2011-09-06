# coding: utf-8
"""
Database access layer for pydici leads module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.db import models
from datetime import datetime, date
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.contrib.admin.models import LogEntry, ContentType
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from taggit.managers import TaggableManager

from pydici.core.utils import compact_text

from pydici.crm.models import Client, BusinessBroker
from pydici.people.models import Consultant, SalesMan
from pydici.actionset.models import ActionState
from pydici.actionset.utils import launchTrigger

SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"

class LeadManager(models.Manager):
    def active(self):
        return self.get_query_set().exclude(state__in=("LOST", "FORGIVEN", "WON", "SLEEPING"))

    def passive(self):
        return self.get_query_set().filter(state__in=("LOST", "FORGIVEN", "WON", "SLEEPING"))
class Lead(models.Model):
    """A commercial lead"""
    STATES = (
            ('QUALIF', ugettext("Qualifying")),
            ('WRITE_OFFER', ugettext("Writting offer")),
            ('OFFER_SENT', ugettext("Offer sent")),
            ('NEGOTIATION', ugettext("Negotiation")),
            ('WON', ugettext("Won")),
            ('LOST', ugettext("Lost")),
            ('FORGIVEN', ugettext("Forgiven")),
            ('SLEEPING', ugettext("Sleeping")),
           )
    name = models.CharField(_("Name"), max_length=200)
    description = models.TextField(blank=True)
    action = models.CharField(_("Action"), max_length=2000, blank=True, null=True)
    sales = models.IntegerField(_(u"Price (k€)"), blank=True, null=True)
    salesman = models.ForeignKey(SalesMan, blank=True, null=True, verbose_name=_("Salesman"))
    staffing = models.ManyToManyField(Consultant, blank=True, limit_choices_to={"active":True})
    external_staffing = models.CharField(_("External staffing"), max_length=300, blank=True)
    responsible = models.ForeignKey(Consultant, related_name="%(class)s_responsible", verbose_name=_("Responsible"), blank=True, null=True)
    business_broker = models.ForeignKey(BusinessBroker, related_name="%(class)s_broker", verbose_name=_("Business broker"), blank=True, null=True)
    paying_authority = models.ForeignKey(BusinessBroker, related_name="%(class)s_paying", verbose_name=_("Paying authority"), blank=True, null=True)
    start_date = models.DateField(_("Starting"), blank=True, null=True)
    due_date = models.DateField(_("Due"), blank=True, null=True)
    state = models.CharField(_("State"), max_length=30, choices=STATES)
    client = models.ForeignKey(Client, verbose_name=_("Client"))
    creation_date = models.DateTimeField(_("Creation"), default=datetime.now())
    deal_id = models.CharField(_("Deal id"), max_length=100, blank=True)
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    send_email = models.BooleanField(_("Send lead by email"), default=True)
    tags = TaggableManager(blank=True)

    objects = LeadManager() # Custom manager that factorise active/passive lead code

    def __unicode__(self):
        return u"%s - %s" % (self.client.organisation, self.name)

    def save(self, force_insert=False, force_update=False):
        self.description = compact_text(self.description)
        if self.deal_id == "":
            # First, subsidiary or broker code
            if self.business_broker:
                deal_id = self.business_broker.code
            else:
                deal_id = self.client.salesOwner.code
            # Then, client company code
            deal_id += self.client.organisation.company.code
            # Then, year in two digits
            deal_id += date.today().strftime("%y")
            # Then, next id available for this prefix
            other_deal_ids = Lead.objects.filter(deal_id__startswith=deal_id).order_by("deal_id")
            other_deal_ids = [item for sublist in other_deal_ids.values_list("deal_id") for item in sublist]
            if other_deal_ids:
                try:
                    deal_id += "%02d" % (int(other_deal_ids[-1][-2:]) + 1)
                except (IndexError, ValueError):
                    # Start at 1
                    deal_id += "01"
            else:
                deal_id += "01"

            self.deal_id = deal_id

        super(Lead, self).save(force_insert, force_update)

    def staffing_list(self):
        staffing = ""
        if self.staffing:
            staffing += ", ".join(x["trigramme"] for x in self.staffing.values())
        if self.external_staffing:
            staffing += ", (%s)" % self.external_staffing
        return staffing

    def update_date_strf(self):
        return self.update_date.strftime(SHORT_DATETIME_FORMAT)
    update_date_strf.short_description = _("Updated")

    def short_description(self):
        max_length = 20
        if len(self.description) > max_length:
            return self.description[:max_length] + "..."
        else:
            return self.description
    short_description.short_description = _("Description")

    def is_late(self):
        """@return: True if due date is today or in the past.
        False if not defined or in the future"""
        if self.due_date and self.due_date <= date.today():
            return True
        else:
            return False

    def get_change_history(self):
        """Return object history action as an action List"""
        actionList = LogEntry.objects.filter(object_id=self.id,
                                              content_type__name="Lead")
        actionList = actionList.select_related().order_by('action_time')
        return actionList

    def done_work(self):
        """Compute done work according to timesheet for all missions of this lead
        @return: (done work in days, done work in euros)"""
        days = 0
        amount = 0
        for mission in self.mission_set.all():
            mDays, mAmount = mission.done_work()
            days += mDays
            amount += mAmount

        return (days, amount)

    def done_work_k(self):
        """Same as done_work, but with amount in keur"""
        days, amount = self.done_work()
        return days, amount / 1000

    def margin(self):
        """Returns mission current margin in euros"""
        if self.sales:
            days, amount = self.done_work()
            return self.sales - amount / 1000
        else:
            return 0

    def unused(self):
        """Returns unused money. ie. sales price minus all planned missions"""
        unused = 0
        if self.sales:
            unused = self.sales
            for mission in self.mission_set.all():
                if mission.price:
                    unused -= mission.price
        return unused

    def actions(self):
        """Returns pending actions"""
        return ActionState.objects.filter(target_id=self.id,
                                          target_type=ContentType.objects.get_for_model(self),
                                          state="TO_BE_DONE")
    @models.permalink
    def get_absolute_url(self):
        return ('pydici.leads.views.detail', [str(self.id)])

    class Meta:
        ordering = ["client__organisation__company__name", "name"]
        verbose_name = _("Lead")

# Signal handling to throw actionset
def leadSignalHandler(sender, **kwargs):
    """Signal handler for new/updated leads"""
    lead = kwargs["instance"]
    targetUser = None
    if lead.responsible:
        targetUser = lead.responsible.getUser()
    if not targetUser:
        # Default to admin
        targetUser = User.objects.filter(is_superuser=True)[0]

    if  kwargs.get("created", False):
        launchTrigger("NEW_LEAD", [targetUser, ], lead)
    if lead.state == "WON":
        launchTrigger("WON_LEAD", [targetUser, ], lead)

# Signal connection to throw actionset
post_save.connect(leadSignalHandler, sender=Lead)
