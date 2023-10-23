#!/usr/bin/env python3
# coding: utf-8

"""
Export users in simple csv format
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import csv
import sys
import os
from os.path import abspath, join, pardir, dirname


# # Setup django envt & django imports
PYDICI_DIR = abspath(join(dirname(__file__), pardir))
os.environ['DJANGO_SETTINGS_MODULE'] = "pydici.settings"

sys.path.append(PYDICI_DIR)  # Add project path to python path

# Ensure we are in the good current working directory (pydici home)
os.chdir(PYDICI_DIR)

# Init and model loading
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# Pydici imports
from people.models import Consultant

output = csv.writer(open("users.csv", "w"))

for c in Consultant.objects.filter(active=True, subcontractor=False):
    u = c.get_user()
    line = ([c.trigramme.lower(),
             *c.name.split(" ", 1),
             u.email,
             c.company.name.lower().replace(" ", "_"),
            ])
    output.writerow(line)


