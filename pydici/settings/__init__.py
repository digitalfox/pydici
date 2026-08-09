# -*- coding: UTF-8 -*-
"""
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import os
import sys

from split_settings.tools import optional, include

env = os.environ.get("PYDICI_ENV", "prod")

if env not in ("dev", "prod"):
    print("You need to set PYDICI_ENV environment variable to 'dev' or 'prod'")
    sys.exit()

include("pydici.py", "django.py", f"{env}.py", optional("local.py"), optional("local-*.py"))


try:
    SECRET_KEY
except NameError as e:
    print(f"{e}. You need to declare it in settings in your settings/local.py file")
    sys.exit()
