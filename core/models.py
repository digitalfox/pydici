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


_FEATURES_CHOICES = (
    ("3rdparties", _("3rd Parties: Access to the 'Third parties' menu")),
    ("contacts_write", _("Contacts, write access: Allow adding, editing, removing contacts")),
    ("leads", _("Leads: Access to the 'Leads' menu")),
    ("leads_list_all", _("Leads, list all: Access to the 'Leads > All leads' menu entry")),
    ("leads_profitability", _("Leads, profitability: Access to the 'Profitability' information in lead description")),
    ("management", _("Management: Access to the 'Management' menu")),
    ("reports", _("Reports: Access to the 'Reports' menu")),
    ("search", _("Search: Allow searching")),
    ("staffing", _("Staffing: Access to staffing features")),
    ("staffing_mass", _("Staffing, mass edit: Access to mass staffing features")),
    ("timesheet_all", _("Timesheet, all: Access to all timesheets of all users")),
    ("timesheet_current_month", _("Timesheet, current month: Access to current month timesheets of all users")),
)

FEATURES = set([x[0] for x in _FEATURES_CHOICES])


class GroupFeature(models.Model):
    """Represents whether a group has access to a certain feature. If Feature
    was a model, this would be the intermediary model between Feature and Group.
    """
    group = models.ForeignKey(Group)
    feature = models.CharField(_("Feature"), max_length=80,
                               choices=_FEATURES_CHOICES)
    class Meta:
        unique_together = (('group', 'feature'))

    def __unicode__(self):
        return unicode(self.group) + '-' + unicode(self.feature)
