# -*- coding: UTF-8 -*-
"""
Development specific settings.
Don't customise this file, use local.py for specific local settings
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
from django.conf import settings

DEBUG = True

SECRET_KEY = "very-very-secret-dev-key"

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'core.middleware.ScopeMiddleware',
    'userswitch.middleware.UserSwitchMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
]

TEMPLATES[0]["OPTIONS"]["debug"] = True

INSTALLED_APPS.extend(['debug_toolbar'])

ALLOWED_HOSTS = ("localhost",)

DEBUG_TOOLBAR_CONFIG = {  # use settings.DEBUG instead of DEBUG to allow django test runner to force settings.DEBUG to False
    'SHOW_TOOLBAR_CALLBACK': lambda request: True if settings.DEBUG else False
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CRISPY_FAIL_SILENTLY = False

# Use to allow LiveServerTestCase to work in serialized_rollback mode in order to preserve migration data during tests
TEST_NON_SERIALIZED_APPS = ['django.contrib.contenttypes',
                            'django.contrib.auth']
