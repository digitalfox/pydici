# coding: utf-8
"""
Database access layer for pydici people module
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: GPL v3 or newer
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from pydici.core.utils import capitalize
from pydici.core.models import Subsidiary

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
    manager = models.ForeignKey("self", null=True, blank=True)
    profil = models.ForeignKey(ConsultantProfile, verbose_name=_("Profil"))

    def __unicode__(self): return self.name

    def save(self, force_insert=False, force_update=False):
        self.name = capitalize(self.name)
        self.trigramme = self.trigramme.upper()
        super(Consultant, self).save(force_insert, force_update)

    class Meta:
        ordering = ["name", ]
        verbose_name = _("Consultant")


class SalesMan(models.Model):
    """A salesman"""
    name = models.CharField(_("Name"), max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"))
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

