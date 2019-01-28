# coding: utf-8
"""
Database access layer for pydici core module
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)

Some parts of Pydici require being a member of a group with access to specific
features.

To check if a user has access to a feature from Python code, use
`utils.user_has_feature()` or the `decorator.pydici_feature()` decorator.

To check for access from a template, use `{% if pydici_feature.<feature_name> %}`.
"""

from django.contrib.auth.models import Group
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.cache import cache


_FEATURES_CHOICES = (
    ("3rdparties", _("3rd Parties: Access to the 'Third parties' menu")),
    ("contacts_write", _("Contacts, write access: Allow adding, editing, removing contacts")),
    ("leads", _("Leads: Access to the 'Leads' menu")),
    ("leads_list_all", _("Leads, list all: Access to the 'Leads > All leads' menu entry")),
    ("leads_profitability", _("Leads, profitability: Access to the 'Profitability' information in lead description")),
    ("management", _("Management: Access to the 'Management' menu")),
    ("menubar", _("Menubar: Show the menubar")),
    ("reports", _("Reports: Access to the 'Reports' menu")),
    ("search", _("Search: Allow searching")),
    ("staffing", _("Staffing: Access to staffing features")),
    ("staffing_mass", _("Staffing, mass edit: Access to mass staffing features")),
    ("timesheet_all", _("Timesheet, all: Access to all timesheets of all users")),
    ("timesheet_current_month", _("Timesheet, current month: Access to current month timesheets of all users")),
    ("billing_management", _("Manage bills, allow to mark bills sent, paid etc.")),
    ("billing_request", _("Create bills and proposed them to billing team ")),
)

FEATURES = set([x[0] for x in _FEATURES_CHOICES])


class GroupFeature(models.Model):
    """Represents whether a group has access to a certain feature. If Feature
    was a model, this would be the intermediary model between Feature and Group.
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    feature = models.CharField(_("Feature"), max_length=80,
                               choices=_FEATURES_CHOICES)
    class Meta:
        unique_together = (('group', 'feature'))

    def __str__(self):
        return str(self.group) + '-' + str(self.feature)


class Parameter(models.Model):
    """Ultra simple parameter defined in database to allow easy editing through admin pages
    This model is intended to be accessed through utils.py get_param to have type checking and cache"""
    PARAMETER_CACHE_KEY = "PYDICI_PARAM_CACHE_%s"
    PARAMETER_TYPES = (("TEXT", _("text")),
                       ("FLOAT", _("float")))
    key= models.CharField(_("Key"), max_length=255, unique=True)
    value = models.CharField(_("Value"), max_length=255)
    type = models.CharField(_("Type"), max_length=30, choices=PARAMETER_TYPES)
    desc = models.CharField(_("Description"), max_length=255)

    def save(self, *args, **kwargs):
        """Invalidate cache for this param"""
        cache.set(self.PARAMETER_CACHE_KEY % self.key, None)
        super(Parameter, self).save(*args, **kwargs)