# coding:utf-8
"""
Actions form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django import forms

from core.forms import UserChoices


class DelegateActionForm(forms.Form):
    """Form to delegate an action to another user"""
    def __init__(self, actionstate_id, *args, **kwargs):
        super(DelegateActionForm, self).__init__(*args, **kwargs)
        #self.fields["user"] = UserChoices(label=_("user"), widget=AutoHeavySelect2Widget(attrs={"id": "deleguate_user_%s" % actionstate_id}))
        self.fields["user"] = forms.ChoiceField(widget=UserChoices(attrs={"id": "deleguate_user_%s" % actionstate_id}))

