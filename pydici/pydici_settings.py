# -*- coding: UTF-8 -*-
# Specific settings for pydici project.
# Pydici specific parameters

import os

# Root dir
PYDICI_ROOTDIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), os.path.pardir)

# Application prefix without leading or trailing slash
# Ex. if defined to 'pydici', index url will be http://my-site.com/pydici/
# Use '' for no prerix. Index url will be http://my-site.com/
PYDICI_PREFIX = "pydici"

# Host base URL (without any prefix and trailing slash) used for absolute link
# used in email
# Ex. "http://www.my-site.com" or "http://localhost:8080"
PYDICI_HOST = "http://localhost:8888"

# Default VAT (Value Added Tax) rate (in %) used for billing.
# Can be overided for each bills. This is just the default proposed value on form
# Value **must** be quoted as a string
# Ex. "19.6"
PYDICI_DEFAULT_VAT_RATE = "20.0"

LEADS_MAIL_FROM = "sebastien.renard@digitalfox.org"
LEADS_MAIL_TO = "sebastien.renard@digitalfox.org"
LEADS_MAIL_SMTP = "www.digitalfox.org"
LEADS_HELP_PAGE = "/my_custom_help_page.html"  # May be absolute or relative

# Filesystem for commercial and mission delivery. It is intented to be
# accessed localy by pydici and exposed though a web server and/or a webdav server
DOCUMENT_PROJECT_PATH = os.path.join(PYDICI_ROOTDIR, 'data/documents')
DOCUMENT_PROJECT_URL = "http://localhost:9999/client/"
DOCUMENT_PROJECT_CLIENT_DIR = u"{name}_{code}"
DOCUMENT_PROJECT_LEAD_DIR = u"{deal_id}_{name}"
DOCUMENT_PROJECT_BUSINESS_DIR = u"commerce"
DOCUMENT_PROJECT_DELIVERY_DIR = u"delivery"
DOCUMENT_PROJECT_INPUT_DIR = u"input"

# INCWO_LOG_DIR must point to a dir where the `incwoimport` command can write.
# It defaults to $PYDICI_PREFIX/incwo-log if not set.
INCWO_LOG_DIR = os.path.join(PYDICI_ROOTDIR, 'incwo-log')
