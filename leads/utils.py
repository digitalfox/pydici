# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Lead models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.utils.translation import  gettext
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.db.models import Count

from leads.learn import compute_leads_state, compute_leads_tags, compute_lead_similarity
from staffing.models import Mission
from leads.models import StateProba, Lead
from leads.tasks import lead_mail_notify, lead_telegram_notify
from core.utils import createProjectTree


def create_default_mission(lead):
    mission = Mission(lead=lead)
    mission.price = lead.sales  # Initialise with lead price
    mission.subsidiary = lead.subsidiary
    mission.responsible = lead.responsible
    try:
        mission.probability = lead.stateproba_set.get(state="WON").score
    except StateProba.DoesNotExist:
        # No state proba, leave mission proba default
        pass
    mission.save()
    # Create default staffing
    mission.create_default_staffing()
    return mission


def post_save_lead(request, lead, created=False, state_changed=False):
    # If this was the last active mission of its client and not more active lead, flag client as inactive
    if len(lead.client.getActiveMissions()) == 0 and len(lead.client.getActiveLeads().exclude(state="WON")) == 0:
        lead.client.active = False
        lead.client.save()

    # create project directories and mark client as active
    if created:
        createProjectTree(lead)
        lead.client.active = True
        lead.client.save()

    if lead.send_email:
        lead_mail_notify.delay(lead.id, from_addr=request.user.email,
                               from_name="%s %s" % (request.user.first_name, request.user.last_name))
        lead.send_email = False
        lead.save()

    lead_telegram_notify.delay(lead.id, created=created, state_changed=state_changed)

    # Compute leads probability
    if lead.state in ("WON", "LOST", "SLEEPING", "FORGIVEN"):
        # Remove leads proba, no more needed
        lead.stateproba_set.all().delete()
        # Learn again. This new lead will now be used to training
        compute_leads_state.delay(relearn=True)
    else:
        # Just update proba for this lead with its new features
        compute_leads_state.delay(relearn=False, leads_id=[lead.id, ])

    # Update lead tags
    compute_leads_tags.delay(relearn=True)

    # update lead similarity model
    compute_lead_similarity.delay(relearn=True)

    # Create or update mission  if needed
    if lead.mission_set.count() == 0:
        if lead.state in ("OFFER_SENT", "NEGOTIATION", "WON"):
            create_default_mission(lead)
            messages.add_message(request, messages.INFO,  gettext("A mission has been initialized for this lead."))

    for mission in lead.mission_set.all():
        if mission.subsidiary != lead.subsidiary:
            mission.subsidiary = lead.subsidiary
            mission.save()
        if lead.state == "WON":
            mission.probability = 100
            mission.active = True
            mission.save()
            messages.add_message(request, messages.INFO,  gettext("Mission's probability has been set to 100%"))
        elif lead.state in ("LOST", "FORGIVEN", "SLEEPING"):
            mission.probability = 0
            mission.active = False
            mission.save()
            messages.add_message(request, messages.INFO,  gettext("According mission has been archived"))


def leads_state_stat(leads):
    """Compute leads statistics in compatible billboard.js format"""
    states = dict(Lead.STATES)
    leads_stat = leads.values("state").order_by("state").annotate(count=Count("state"))
    leads_stat = [[mark_safe(states[s['state']]), s['count']] for s in leads_stat]  # Use state label
    return leads_stat