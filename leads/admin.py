# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: GPL v3 or newer
"""

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from ajax_select import make_ajax_form
from ajax_select.admin import AjaxSelectAdmin

from datetime import datetime

from pydici.leads.models import Lead
from pydici.staffing.models import Mission, Staffing

from pydici.leads.forms import LeadForm

from pydici.core.utils import send_lead_mail, capitalize


class LeadAdmin(AjaxSelectAdmin):
    list_display = ("name", "client", "short_description", "responsible", "salesman", "business_broker", "state", "due_date", "update_date_strf")
    fieldsets = [
        (None, {"fields": ["name", "client", "description", "action"]}),
        ("État et suivi", {"fields": ["responsible", "salesman", "business_broker", "state", "due_date", "start_date"]}),
        ("Staffing", {"fields": ["staffing", "external_staffing", "sales"]}),
        (None, {"fields": ["send_email", ]})
        ]
    ordering = ("creation_date",)
    actions = None
    filter_horizontal = ["staffing"]
    list_filter = ["state", ]
    date_hierarchy = "update_date"
    search_fields = ["name", "description", "action",
                     "responsible__name", "responsible__trigramme",
                     "salesman__name", "salesman__trigramme",
                     "client__contact__name", "client__organisation__company__name",
                     "client__organisation__name",
                     "staffing__trigramme", "staffing__name"]
    form = LeadForm

    def save_model(self, request, obj, form, change):
        mail = False
        if obj.send_email:
            mail = True
            obj.send_email = False
        obj.save()
        form.save_m2m() # Save many to many relations
        if mail:
            try:
                fromAddr = request.user.email or "noreply@noreply.com"
                send_lead_mail(obj, request, fromAddr=fromAddr,
                               fromName="%s %s" % (request.user.first_name, request.user.last_name))
                request.user.message_set.create(message=ugettext("Lead sent to business mailing list"))
            except Exception, e:
                request.user.message_set.create(message=ugettext("Failed to send mail: %s") % e)

        # Create or update mission object if needed
        try:
            mission = Mission.objects.get(lead=obj)
            mission_does_not_exist = False
        except Mission.DoesNotExist:
            mission = Mission(lead=obj) # Mission is saved below if needed
            mission_does_not_exist = True

        if obj.state in ("OFFER_SENT", "NEGOTIATION", "WON") and mission_does_not_exist:
            currentMonth = datetime.now()
            mission.lead = obj
            mission.save()
            # Create default staffing
            for consultant in obj.staffing.all():
                staffing = Staffing()
                staffing.mission = mission
                staffing.consultant = consultant
                staffing.staffing_date = currentMonth
                staffing.update_date = currentMonth
                staffing.last_user = "-"
                staffing.save()
            request.user.message_set.create(message=ugettext("A mission has been initialized for this lead."))
        if obj.state == "WON":
            mission.probability = 100
            mission.active = True
            mission.save()
            request.user.message_set.create(message=ugettext("Mission's probability has been set to 100%"))
        elif obj.state in ("LOST", "FORGIVEN", "SLEEPING"):
            mission.probability = 0
            mission.active = False
            mission.save()
            request.user.message_set.create(message=ugettext("According mission has been archived"))


admin.site.register(Lead, LeadAdmin)
