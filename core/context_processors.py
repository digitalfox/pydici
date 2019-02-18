# -*- coding: UTF-8 -*-
"""
Pydici core context processors
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from collections import defaultdict
from importlib import import_module

from django.conf import settings

from core.utils import user_has_feature


class FeatureWrapper(object):
    def __init__(self, user):
        self.user = user

    def __getitem__(self, feature):
        return user_has_feature(self.user, str(feature))

    def __contains__(self, feature):
        return bool(self[feature])


def feature(request):
    """
    Returns context variables to check if the current user has access to Pydici
    features.
    """
    if hasattr(request, 'user'):
        user = request.user
    else:
        from django.contrib.auth.models import AnonymousUser
        user = AnonymousUser()

    return {
        'pydici_feature': FeatureWrapper(user),
    }


_menu_templates = None


def _init_menu_templates():
    global _menu_templates
    _menu_templates = defaultdict(list)
    for app in settings.INSTALLED_APPS:
        try:
            mod = import_module(app + '.menus')
        except ImportError:
            continue
        for menu_name, template_name in list(mod.get_menus().items()):
            _menu_templates[menu_name].append(template_name)


class MenuWrapper(object):
    def __getitem__(self, name):
        return _menu_templates.get(name)

    def __contains__(self, name):
        return bool(self[name])


def menu(request):
    """Provides a way for applications to extend the Pydici menubar.

    An application willing to add a new entry to the menubar must provide a `menus.py` file which
    contain a `get_menus()` function. This function must return a dictionary of
    menu_name => template_name items.

    For example if an application wants to extend the "Foo" menu, it can provides a `menus.py`
    with the following content:

        def get_menus():
            return { 'foo': 'myapp/foo_menu.html' }

    The content of the 'myapp/foo_menu.html' template will be inserted in the Foo menu.

    Note: for this to work, `templates/core/_pydici_menu.html` must contain hooks for all top-level
    menu items. These hooks are implemented using the `pydici_menu` variable exposed by this context
    processor. Here is how such a hook would look for the "Foo" menu.

        ...
        <li>
            <a href="#" class="dropdown-toggle" data-toggle="dropdown">Foo
                <span class='caret'></span>
            </a>
            <ul class="dropdown-menu" role="menu">
                <li><a href='bar.html'>Bar</a></li>
                <li><a href='baz.html'>Baz</a></li>
                {% if pydici_menu.foo %}
                    {% for name in pydici_menu.foo %}
                        {% include name %}
                    {% endfor %}
                {% endif %}
            </ul>
        </li>
        ...

    With such code, the content of `myapp/foo_menu.html` would be inserted after the "Baz" menu
    item.
    """
    if _menu_templates is None:
        _init_menu_templates()
    return {
        'pydici_menu': MenuWrapper(),
    }
