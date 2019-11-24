# coding:utf-8
"""
Core form setup
@author: Sébastien Renard <Sebastien.Renard@digitalfox.org>
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django import forms
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from taggit.models import Tag


class PydiciSelect2WidgetMixin(object):
    """widget mixin to add security and default attributes"""
    def __init__(self, *args, **kwargs):
        kwargs['data_view'] = 'pydici-select2-view'
        super(PydiciSelect2WidgetMixin, self).__init__(*args, **kwargs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        """Set select2's attributes."""
        default_attrs = {"data-minimum-input-length": 0, "data-width": "100%", "data-theme": "bootstrap"}
        attrs = super().build_attrs(default_attrs, extra_attrs=extra_attrs)
        return attrs

class SearchForm(forms.Form):
    search = forms.CharField(max_length=100)


class UserChoices(PydiciSelect2WidgetMixin, ModelSelect2Widget):
    model = User
    search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains"]

    def get_queryset(self):
        return User.objects.filter(is_active=True).order_by("username")

    def label_from_instance(self, user):
        return user.get_full_name()


class TagChoices(ModelSelect2Widget):
    model = Tag
    search_fields = ["name__icontains"]

    def get_queryset(self):
        return Tag.objects.all()

class TagMChoices(ModelSelect2MultipleWidget):
    model = Tag
    search_fields = ["name__icontains"]

    def get_queryset(self):
        return Tag.objects.all()


class PydiciCrispyBaseForm(object):
    """A base form to be subclassed. Factorise common things of all pydici crispy forms"""
    def __init__(self, *args, **kwargs):
        super(PydiciCrispyBaseForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()  # For standard form use
        self.inline_helper = FormHelper()  # For inline (ie embeded in an other form)
        self.inline_helper.form_tag = False
        self.submit = Submit("Submit", _("Save"))
        self.submit.field_classes = "btn btn-default"


class PydiciCrispyModelForm(PydiciCrispyBaseForm, forms.ModelForm):
    """pydici model forms"""
    pass

class PydiciCrispyForm(PydiciCrispyBaseForm, forms.Form):
    """pydici standard (non-model) forms"""
    pass