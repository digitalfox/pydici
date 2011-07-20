# coding: utf-8
"""
Database access layer for pydici action set module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from datetime import datetime

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.contrib.auth.models import User


class ActionSet(models.Model):
    """Set of action that needs to be done at defined step of a process"""
    name = models.CharField(_("Name"), max_length=50)

    def __unicode__(self): return self.name

    def start(self, user):
        """Start this action set for given user"""
        for action in self.action_set.all():
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
    action = models.ForeignKey(Action)
    done = models.BooleanField(_(u"Réalisation"), default=False)
    done.db_index = True
    user = models.ForeignKey(User)
    creation_date = models.DateTimeField(_("Creation"), default=datetime.now())
    update_date = models.DateTimeField(_("Updated"), auto_now=True)
