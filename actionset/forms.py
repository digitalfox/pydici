# coding:utf-8
"""
Actions form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django import forms
from django.utils.translation import ugettext as _

from django_select2.widgets import AutoHeavySelect2Widget


from core.forms import UserChoices


class LaunchActionSetForm(forms.Form):
    """Form to manually launch an action set"""
    actionset = forms.fields.HiddenInput()

    def __init__(self, actionset_id, *args, **kwargs):
        super(LaunchActionSetForm, self).__init__(*args, **kwargs)
        self.fields["user"] = UserChoices(label=_("user"), widget=AutoHeavySelect2Widget(attrs={"id": "actionset_target_user_%s" % actionset_id}))


class DelegateActionForm(forms.Form):
    """Form to delegate an action to another user"""
    def __init__(self, actionstate_id, *args, **kwargs):
        super(DelegateActionForm, self).__init__(*args, **kwargs)
        self.fields["user"] = UserChoices(label=_("user"), widget=AutoHeavySelect2Widget(attrs={"id": "deleguate_user_%s" % actionstate_id}))
