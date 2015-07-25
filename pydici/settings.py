# -*- coding: UTF-8 -*-
# Django settings for pydici project.

import os
from pydici_settings import *
DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('Sébastien Renard', 'sebastien@digitalfox.org'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'pydici.db'
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
# TIME_ZONE = 'America/Chicago'
TIME_ZONE = 'Europe/Paris'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'fr-fr'
LOCALE_PATHS = (os.path.join(PYDICI_ROOTDIR, "locale"),)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True
USE_L10N = True
USE_THOUSAND_SEPARATOR = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
if PYDICI_PREFIX:
    MEDIA_URL = "/%s/media/" % PYDICI_PREFIX
else:
    # Needed for empty prefix (equivalent to "/")
    MEDIA_URL = "/media/"

# STATICFILES_DIRS = (os.path.join(PYDICI_ROOTDIR, 'media'),)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(PYDICI_ROOTDIR, "static")

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '-)^_522$p_b6ckz_94&o_en4th6ug&gxpe$!@f^6fjim0j=_)p'


# Template processors, used to add session access wihtin templates
TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.contrib.messages.context_processors.messages",
    "django.core.context_processors.request",
    "core.context_processors.feature",
    "core.context_processors.menu",
)

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

if DEBUG:
    MIDDLEWARE_CLASSES.append('userswitch.middleware.UserSwitchMiddleware')

ROOT_URLCONF = 'pydici.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(PYDICI_ROOTDIR, 'templates'),
)

PYDICI_APPS = [
    'core',
    'people',
    'leads',
    'staffing',
    'crm',
    'billing',
    'expense',
    'actionset',
    'batch.incwo',
]

INSTALLED_APPS = [
    # Django apps
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.admindocs',
    ] + PYDICI_APPS + [
    # Third party apps
    'django_extensions',
    'django.contrib.staticfiles',  # Static files are served by web server in production mode, but this apps allow collectstatic
    'taggit',
    'taggit_templatetags',
    'permissions',
    'workflows',
    'django_tables2',
    'crispy_forms',
    'django_select2',
]

if DEBUG:
    INSTALLED_APPS.extend(('debug_toolbar',
            ))

WSGI_APPLICATION = "pydici.wsgi.application"
ALLOWED_HOSTS = ("localhost",)

INTERNAL_IPS = ('127.0.0.1',)
DEBUG_TOOLBAR_CONFIG = {"DISABLE_PANELS": "debug_toolbar.panels.redirects.RedirectsPanel",
                        "JQUERY_URL": "/%s/media/js/jquery-1.11.2.min.js" % PYDICI_PREFIX
                        }

if PYDICI_PREFIX:
    LOGIN_URL = "/%s/forbiden" % PYDICI_PREFIX
else:
    LOGIN_URL = "/forbiden"

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CRISPY_TEMPLATE_PACK = 'bootstrap3'
CRISPY_FAIL_SILENTLY = not DEBUG
AUTO_RENDER_SELECT2_STATICS = False
