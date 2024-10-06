# -*- coding: UTF-8 -*-
# Specific settings for pydici project.
# Pydici specific parameters

import os
from django.utils.translation import gettext_lazy as _

# Root dir
PYDICI_ROOTDIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), os.path.pardir, os.path.pardir)

# Default VAT (Value Added Tax) rate (in %) used for billing.
# Can be overrode for each bill. This is just the default proposed value on form
# Value **must** be quoted as a string
# Ex. "19.6"
PYDICI_DEFAULT_VAT_RATE = "20.0"


# Filesystem for commercial and mission delivery. It is intented to be
# accessed localy by pydici and exposed though a web server and/or a webdav server
# set to None in order to disable
DOCUMENT_PROJECT_PATH = os.path.join(PYDICI_ROOTDIR, 'data/documents')
# URL for directories
DOCUMENT_PROJECT_URL_DIR = "http://localhost:9999/client/"
# URL for files (may be the same as above)
DOCUMENT_PROJECT_URL_FILE = "http://localhost:9999/client/"
DOCUMENT_PROJECT_CLIENT_DIR = "{name}_{code}"
DOCUMENT_PROJECT_LEAD_DIR = "{deal_id}_{name}"
DOCUMENT_PROJECT_BUSINESS_DIR = "commerce"
DOCUMENT_PROJECT_DELIVERY_DIR = "delivery"
DOCUMENT_PROJECT_INPUT_DIR = "input"

# can be "cycle" or "keyboard"
TIMESHEET_INPUT_METHOD = "cycle"
TIMESHEET_DAY_DURATION = 7

# Telegram integration
TELEGRAM_IS_ENABLED = False  # Wether to enable or not Telegram notifications
TELEGRAM_TOKEN = "123123:ABCABC"  # Your Bot Token.
TELEGRAM_CHAT = {
                    "new_leads" : [-71462389,], # List of chat_id to send new leads notif to
                    "leads_update": [-71462389,], # List of chat_id to send leads udpate notif to
                }
TELEGRAM_STICKERS = {
                        "happy": "BQADBAADQAADyIsGAAGMQCvHaYLU_AI",
                        "sad": "BQADBAADFQADyIsGAAEO_vKI0MR5bAI",
                    }
TELEGRAM_CHAT_MANAGER_LEVEL = 4  # Every people with level < to his will be notified individually if concerned

# Default company logo
COMPANY_LOGO = "/media/pydici/company_logo.png"

# Achievements configuration
ACHIEVEMENTS = {
    "MISSION_COUNT": [(_("rookie"), 0), (_("pro"), 50), (_("veteran"), 100), (_("emperor"), 200), (_("grandmaster"), 300)],
    "ACTIVE_MISSION_COUNT": [(_("minimalist"), 0), (_("busy"), 10), (_("juggler"), 15), (_("collector"), 25), (_("archivist killer"), 50)],
    "TURNOVER": [(_("rookie"), 0), (_("pro"), 500), (_("good winner"), 1_000), (_("Cresus"), 2_000), (_("Picsou"), 5_000)],
    "LAST_YEAR_TURNOVER": [(_("rookie"), 0), (_("good winner"), 100), (_("alchemist"), 150), (_("wolf of Wall Street"), 250), (_("grandmaster"), 350)],
    "LONGEST_MISSION": [(_("rookie"), 0), (_("sprinter"), 50), (_("marathoner"), 100), (_("survivor"), 200), (_("grandmaster"), 500)],
    "LONGEST_LEAD": [(_("premature"), 0), (_("patient"), 50), (_("resilient"), 100), (_("tireless"), 200), (_("resigned"), 500)],
    "MAX_MISSION_PER_MONTH": [(_("rookie"), 0), (_("multithread"), 3), (_("ubiquitous"), 5), (_("ninja"), 10), (_("grandmaster"), 15)],
}
