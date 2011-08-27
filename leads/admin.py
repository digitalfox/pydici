# coding:utf-8
"""
Django administration setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from ajax_select.admin import AjaxSelectAdmin

from pydici.leads.models import Lead
from pydici.staffing.models import Mission
from pydici.leads.forms import LeadForm
from pydici.core.utils import send_lead_mail


class LeadAdmin(AjaxSelectAdmin):
    list_display = ("name", "client", "responsible", "salesman", "business_broker", "state", "due_date", "update_date_strf")
    fieldsets = [
        (None, {"fields": ["name", "client", "description", "action"]}),
        (_("State and tracking"), {"fields": ["responsible", "state", "due_date", "start_date", "deal_id"]}),
        (_("Commercial"), {"fields": ["sales", "business_broker", "paying_authority", "salesman", ]}),
        (_("Staffing"), {"fields": ["staffing", "external_staffing"]}),
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
        if obj.mission_set.count() == 0:
            if obj.state in ("OFFER_SENT", "NEGOTIATION", "WON"):
                mission = Mission(lead=obj)
                mission.price = obj.sales # Initialise with lead price
                mission.save()
                # Create default staffing
                mission.create_default_staffing()
                request.user.message_set.create(message=ugettext("A mission has been initialized for this lead."))

        for mission in obj.mission_set.all():
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
