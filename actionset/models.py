# coding: utf-8
"""
Database access layer for pydici action set module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import datetime

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

class ActionSet(models.Model):
    """Set of action that needs to be done when triggered by a process"""
    ACTIONSET_TRIGGERS = (
            ('NEW_LEAD', ugettext("When a lead is created ")),
            ('WON_LEAD', ugettext("When a lead is won ")),
            ('NEW_MISSION', ugettext("When a mission is created")),
            ('ARCHIVED_MISSION', ugettext("When mission is archived")),
           )
    name = models.CharField(_("Name"), max_length=50)
    description = models.TextField(_("Description"), blank=True)
    trigger = models.CharField(_("Trigger"), max_length=50, choices=ACTIONSET_TRIGGERS, blank=True, null=True)
    active = models.BooleanField(_("Active"), default=True)

    def __unicode__(self): return self.name

    def start(self, user, targetObject=None):
        """Start this action set for given user"""
        if not self.active:
            return
        for action in self.action_set.all():
            if targetObject:
                ActionState.objects.create(action=action, user=user, target=targetObject)
            else:
                ActionState.objects.create(action=action, user=user)

class Action(models.Model):
    """Single action"""
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    actionset = models.ForeignKey(ActionSet)

    def __unicode__(self):
        return u"%s/%s" % (self.actionset, self.name)


class ActionState(models.Model):
    """Track actions done and to be done by users"""
    ACTION_STATES = (("TO_BE_DONE", _("To be done")),
                     ("DONE", _("Done")),
                     ("NA", _("N/A")))
    action = models.ForeignKey(Action)
    state = models.CharField(_("State"), max_length=50, choices=ACTION_STATES, default=ACTION_STATES[0][0])
    state.db_index = True
    user = models.ForeignKey(User)
    creation_date = models.DateTimeField(_("Creation"), default=datetime.now())
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
    target_type = models.ForeignKey(ContentType, verbose_name=_(u"Target content type"), blank=True, null=True)
    target_id = models.PositiveIntegerField(_(u"Content id"), blank=True, null=True)
    target = generic.GenericForeignKey(ct_field="target_type", fk_field="target_id")

    def __unicode__(self):
        if self.target:
            return u"%s (%s)" % (self.action, self.target)
        else:
            return unicode(self.action)
