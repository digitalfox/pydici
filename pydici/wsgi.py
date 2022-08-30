# coding: utf-8
"""
WSGI Wrapper for production deployment
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import os

import sys

pydici_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), os.path.pardir)
if pydici_path not in sys.path:
    sys.path.append(pydici_path)
    sys.path.append(os.path.join(pydici_path,"pydici"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pydici.settings")

# This application object is used by the development server
# as well as any WSGI server configured to use this file.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
