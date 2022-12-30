# coding: utf-8
"""
Database access layer for pydici leads module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import os

from django.db import models
from datetime import datetime, date, timedelta
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.contrib.admin.models import ContentType
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.db.models import Q, Sum
from django.urls import reverse
from django.conf import settings

from taggit.managers import TaggableManager
from auditlog.models import AuditlogHistoryField

from core.utils import compact_text
from crm.models import Client, BusinessBroker, Subsidiary
from people.models import Consultant, SalesMan
from billing.utils import get_client_billing_control_pivotable_data
from core.utils import createProjectTree, disable_for_loaddata, getLeadDirs, cacheable


SHORT_DATETIME_FORMAT = "%d/%m/%y %H:%M"


class LeadManager(models.Manager):
    PASSIVE_STATES = ("LOST", "FORGIVEN", "WON", "SLEEPING")

    def active(self):
        today = datetime.today()
        delay = timedelta(days=1)
        return self.get_queryset().exclude(Q(state__in=self.PASSIVE_STATES) & Q(update_date__lt=today-delay))

    def passive(self):
        return self.get_queryset().filter(state__in=self.PASSIVE_STATES)


class Lead(models.Model):
    """A commercial lead"""
    STATES = (
            ('QUALIF',  gettext("Qualifying")),
            ('WRITE_OFFER',  gettext("Writting offer")),
            ('OFFER_SENT',  gettext("Offer sent")),
            ('NEGOTIATION',  gettext("Negotiation")),
            ('WON',  gettext("Won")),
            ('LOST',  gettext("Lost")),
            ('FORGIVEN',  gettext("Forgiven")),
            ('SLEEPING',  gettext("Sleeping")),
           )
    name = models.CharField(_("Name"), max_length=200)
    description = models.TextField(blank=True)
    administrative_notes = models.TextField(_("Administrative notes"), blank=True)
    action = models.CharField(_("Action"), max_length=2000, blank=True, null=True)
    sales = models.DecimalField(_("Price (k€)"), blank=True, null=True, max_digits=10, decimal_places=3)
    salesman = models.ForeignKey(SalesMan, blank=True, null=True, verbose_name=_("Salesman"), on_delete=models.SET_NULL)
    staffing = models.ManyToManyField(Consultant, blank=True, limit_choices_to={"active": True, "productive": True})
    external_staffing = models.CharField(_("External staffing"), max_length=300, blank=True)
    responsible = models.ForeignKey(Consultant, related_name="%(class)s_responsible", verbose_name=_("Responsible"), blank=True, null=True, on_delete=models.SET_NULL)
    business_broker = models.ForeignKey(BusinessBroker, related_name="%(class)s_broker", verbose_name=_("Business broker"), blank=True, null=True, on_delete=models.SET_NULL)
    paying_authority = models.ForeignKey(BusinessBroker, related_name="%(class)s_paying", verbose_name=_("Paying authority"), blank=True, null=True, on_delete=models.SET_NULL)
    start_date = models.DateField(_("Starting"), blank=True, null=True)
    due_date = models.DateField(_("Due"), blank=True, null=True)
    state = models.CharField(_("State"), max_length=30, choices=STATES, default=STATES[0][0])
    state.db_index = True
    client = models.ForeignKey(Client, verbose_name=_("Client"), on_delete=models.CASCADE)
    creation_date = models.DateTimeField(_("Creation"), auto_now_add=True)
    deal_id = models.CharField(_("Deal id"), max_length=100, blank=True)
    client_deal_id = models.CharField(_("Client deal id"), max_length=100, blank=True)
    deal_id.db_index = True
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    send_email = models.BooleanField(_("Send lead by email"), default=True)
    tags = TaggableManager(blank=True)
    subsidiary = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), on_delete=models.CASCADE)
    external_id = models.CharField(max_length=200, default=None, blank=True, null=True, unique=True)

    objects = LeadManager()  # Custom manager that factorise active/passive lead code
    history = AuditlogHistoryField()

    @cacheable("Lead.__str__%(id)s", 3)
    def __str__(self):
        return "%s - %s" % (self.client.organisation, self.name)

    def save(self, force_insert=False, force_update=False):
        self.description = compact_text(self.description)
        self.administrative_notes = compact_text(self.administrative_notes)
        if self.deal_id == "":
            # First, client company code
            deal_id = str(self.client.organisation.company.code)
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
            staffing += ", ".join([x["trigramme"] for x in list(self.staffing.values())])
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

    def done_work(self):
        """Compute done work according to timesheet for all missions of this lead
        @return: (done work in days, done work in euros)"""
        days = 0
        amount = 0
        for mission in self.mission_set.all():
            mDays, mAmount = mission.done_work()
            days += mDays
            amount += mAmount

        return days, amount

    def done_work_k(self):
        """Same as done_work, but with amount in keur"""
        days, amount = self.done_work()
        return days, amount / 1000

    def unattributed(self):
        """Returns non attributed amount to missions. ie. sales price minus all missions amount"""
        unused = 0
        if self.sales:
            unused = self.sales
            for mission in self.mission_set.all():
                if mission.price:
                    unused -= mission.price
        return unused

    def objectiveMargin(self, startDate=None, endDate=None):
        """Compute margin over rate objective of all lead's missions
        @param startDate: starting date to consider. This date is included in range. If None, start date is the begining of each mission
        @param endDate: ending date to consider. This date is excluded from range. If None, end date is last timesheet for each mission.
        @return: dict where key is consultant, value is cumulated margin over objective
        @see: for global sum, see totalMarginObjectives()"""
        leadMargin = {}
        for mission in self.mission_set.all():
            missionMargin = mission.objectiveMargin(startDate, endDate)
            for consultant in missionMargin:
                if consultant in leadMargin:
                    leadMargin[consultant] += missionMargin[consultant]
                else:
                    leadMargin[consultant] = missionMargin[consultant]
        return leadMargin

    def totalObjectiveMargin(self, startDate=None, endDate=None):
        """Compute total margin objective of all lead's missions for all consultants
        @return: int in k€
        @see: for per consultant, look at marginObjectives()"""
        return sum(self.objectiveMargin(startDate, endDate).values())

    def margin(self):
        """Compute sum of missions margin. For timespent mission, only objective margin is computed, for fixed price, we also consider
        price minus total work done and forecasted work if mission is archived
        @:return: margin in k€"""
        margin = 0
        for mission in self.mission_set.all():
            margin += sum(mission.objectiveMargin().values())
            if mission.billing_mode == "FIXED_PRICE" and not mission.active:
                margin += mission.remaining(mode="target") * 1000
        return margin

    @cacheable("Lead.__billed__%(id)s", 3)
    def billed(self):
        """Total amount billed for this lead"""
        return list(self.clientbill_set.filter(state__in=("1_SENT", "2_PAID")).aggregate(Sum("amount")).values())[0] or 0

    def still_to_be_billed(self, include_current_month=True, include_fixed_price=True):
        """Amount that still need to be billed"""
        to_bill = 0
        if include_current_month:
            end = date.today()
        else:
            end = date.today().replace(day=1)
        for mission in self.mission_set.all():
            if mission.billing_mode == "TIME_SPENT" or mission.billing_mode is None:
                to_bill += float(mission.done_work_period(None, end)[1])
            elif mission.billing_mode == "FIXED_PRICE" and include_fixed_price:
                # TODO: sum as well subcontractor bills for fixed priced mission
                if mission.price:
                    to_bill += float(mission.price * 1000)
        to_bill += float(list(self.expense_set.filter(chargeable=True).aggregate(Sum("amount")).values())[0] or 0)
        return to_bill - float(self.billed())

    def billing_control_data(self):
        return get_client_billing_control_pivotable_data(filter_on_lead=self)

    def checkDeliveryDoc(self):
        """Ensure delivery doc are put on file server if lead is won and archived
        @return: True is doc is ok, else False"""
        if self.state == "WON" and self.mission_set.filter(active=True).count() == 0:
            clientDir, leadDir, businessDir, inputDir, deliveryDir = getLeadDirs(self)
            if not deliveryDir:
                return True  # if path is not defined, not needs to go further
            try:
                if len(os.listdir(deliveryDir)) == 0:
                    return False
            except OSError:
                # Document directory may not exist or may not be accessible
                return False
        return True

    def checkBusinessDoc(self):
        """Ensure business doc are put on file server if business propoal has been sent
        @return: True is doc is ok, else False"""
        if self.state in ("WON", "OFFER_SENT", "NEGOTIATION"):
            clientDir, leadDir, businessDir, inputDir, deliveryDir = getLeadDirs(self)
            if not businessDir:
                return True  # if path is not defined, not needs to go further
            try:
                if len(os.listdir(businessDir)) == 0:
                    return False
            except OSError:
                # Document directory may not exist or may not be accessible
                return False
        return True

    def getStateProba(self):
        """Returns a list of tuple (proba_code, proba label, proba score) for lead state probability"""
        states = dict(Lead.STATES)
        return [(proba.state, states[proba.state], proba.score) for proba in self.stateproba_set.all().order_by("-score")]

    def getDocURL(self):
        """@return: URL to reach this lead base directory"""
        (clientDir, leadDir, businessDir, inputDir, deliveryDir) = getLeadDirs(self)
        if leadDir:
            url = settings.DOCUMENT_PROJECT_URL_DIR + leadDir[len(settings.DOCUMENT_PROJECT_PATH):]
            return url
        else:
            return ""

    def get_absolute_url(self):
        return reverse('leads:detail', args=[str(self.id)])

    class Meta:
        ordering = ["client__organisation__company__name", "name"]
        verbose_name = _("Lead")


class StateProba(models.Model):
    """Lead state probability"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    state = models.CharField(_("State"), max_length=30, choices=Lead.STATES)
    score = models.IntegerField(_("Score"))
