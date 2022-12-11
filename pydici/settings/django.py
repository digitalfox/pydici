# -*- coding: UTF-8 -*-
# Django settings for pydici project.

import os
import sys

ADMINS = (
     ('Sébastien Renard', 'sebastien@digitalfox.org'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': "pydici",
        'USER': "pydici" if "test" not in sys.argv else "root",
        'PASSWORD': "pydici" if "test" not in sys.argv else "root",
        'HOST': "mariadb",
    }
}


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': 'memcached:11211',

    },
    'select2': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': 'memcached:11211',
        'TIMEOUT': 60*15,
    },

}

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

TIME_ZONE = 'Europe/Paris'

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
MEDIA_ROOT = ""

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = "/media/"

# STATICFILES_DIRS = (os.path.join(PYDICI_ROOTDIR, 'media'),)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(PYDICI_ROOTDIR, "static")

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

ROOT_URLCONF = 'pydici.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [os.path.join(PYDICI_ROOTDIR, 'templates')],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': ("django.contrib.auth.context_processors.auth",
                               "django.template.context_processors.debug",
                               "django.template.context_processors.i18n",
                               "django.template.context_processors.media",
                               "django.template.context_processors.static",
                               "django.template.context_processors.tz",
                               "django.contrib.messages.context_processors.messages",
                               "django.template.context_processors.request",
                               "core.context_processors.feature",
                               "core.context_processors.scope",
                               ),
                },
}]

PYDICI_APPS = [
    'core',
    'people',
    'leads',
    'staffing',
    'crm',
    'billing',
    'expense',
    'actionset'
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
    'taggit_templatetags2',
    'django_tables2',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_select2',
    'django_celery_results',
    'django_celery_beat',
    'auditlog',
    'django_countries',
]


WSGI_APPLICATION = "pydici.wsgi.application"

LOGIN_URL = "/forbidden"  # URL used to redirect users without enough rights

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
SELECT2_CACHE_BACKEND = 'select2'
SELECT2_JS = ''
SELECT2_CSS = ''
TAGGIT_LIMIT = 200

# since django 3.2, default PK field has changed from autofield (integer) to bigint. Set here previous default.
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null_handler': {
            'level': 'ERROR',
            'class': 'logging.NullHandler',
        },
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'weasyprint': {
            'level': 'ERROR',
            'handlers': ['null_handler'],
        },
        'fontTools': {
            'level': 'ERROR',
            'handlers': ['null_handler'],
        },
    }
}

# Celery configuration
CELERY_BROKER_URL = "redis://redis"
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "default"
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_ENABLE_UTC = False
DJANGO_CELERY_BEAT_TZ_AWARE = False
CELERY_TIMEZONE = 'Europe/Paris'

# Audit log configuration
AUDITLOG_INCLUDE_TRACKING_MODELS = (
    {
        "model": "leads.Lead",
        "exclude_fields": ["id", "description", "administrative_notes", "send_email", "tagged_items", "update_date", "creation_date"],
        "m2m_fields": ["staffing"],
    },
    {
        "model": "staffing.Mission",
        "exclude_fields": ["id", "probability", "probability_auto", "update_date", ]
    },
    {
        "model": "expense.Expense",
        "exclude_fields": ["id", "creation_date", "update_date", "workflow_in_progress", "expensePayment"]
    },
    {
        "model": "billing.ClientBill",
        "exclude_fields": ["id", "creation_date", "update_date", "workflow_in_progress", "expensePayment"],
        "m2m_fields": ["expenses"],
    }
)
