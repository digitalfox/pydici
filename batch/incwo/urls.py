# -*- coding: UTF-8 -*-
"""
URL dispatcher for Incwo module
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from django.conf.urls import url
import batch.incwo.views as v


incwo_urls = [url(r'^$', v.imports),
              url(r'^(P<log_dir>[-:T0-9]+)$', v.details),
            ]
