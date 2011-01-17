# -*- coding: UTF-8 -*-
# Django settings for pydici project.

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('Sébastien Renard', 'sebastien@digitalfox.org'),
)

MANAGERS = ADMINS


# Pydici specific parameters

# Application prefix without leading or trailing slash
# Ex. if defined to 'pydici', index url will be http://my-site.com/pydici/
# Use '' for no prerix. Index url will be http://my-site.com/
PYDICI_PREFIX = "pydici"

# Host base URL (without any prefix and trailing slash) used for absolute link
# used in email
# Ex. "http://www.my-site.com" or "http://localhost:8080"
PYDICI_HOST = "http://localhost:8888"

LEADS_MAIL_FROM = "sebastien.renard@digitalfox.org"
LEADS_MAIL_TO = "sebastien.renard@digitalfox.org"
LEADS_MAIL_SMTP = "www.digitalfox.org"
LEADS_HELP_PAGE = "/my_custom_help_page.html" # May be absolute or relative

AJAX_LOOKUP_CHANNELS = {
    'consultant' : ('people.lookups', 'ConsultantLookup'),
    'salesman' : ('people.lookups', 'SalesmanLookup'),
    'business_broker' : ('crm.lookups', 'BusinessBrokerLookup'),
    'client' : ('crm.lookups', 'ClientLookup'),
    'mission' : ('staffing.lookups', 'MissionLookup'),
    'lead' : ('leads.lookups', 'LeadLookup'),
}


# Database settings
DATABASE_ENGINE = 'sqlite3'           # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = 'pydici.db'             # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
#TIME_ZONE = 'America/Chicago'
TIME_ZONE = 'Europe/Paris'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'fr-fr'

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

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '-)^_522$p_b6ckz_94&o_en4th6ug&gxpe$!@f^6fjim0j=_)p'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

ROOT_URLCONF = 'pydici.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    '/home/fox/prog/workspace/pydici/templates'
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'debug_toolbar',
    'pydici.core',
    'pydici.people',
    'pydici.leads',
    'pydici.staffing',
    'pydici.crm',
    'pydici.billing',
    'ajax_select'
)

INTERNAL_IPS = ('127.0.0.1',)
DEBUG_TOOLBAR_CONFIG = { "INTERCEPT_REDIRECTS" : False }

if PYDICI_PREFIX:
    LOGIN_URL = "/%s/forbiden" % PYDICI_PREFIX
else:
    LOGIN_URL = "/forbiden"

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
