# -*- coding: UTF-8 -*-
"""
Incwo import views. Http requests are processed here.
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import json
import os

from datetime import datetime

from core.decorator import pydici_feature

from django.conf import settings
from django.shortcuts import render


class LogInfo(object):
    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.date = datetime.strptime(log_dir, "%Y-%m-%dT%H:%M:%S")
        try:
            json_path = os.path.join(settings.INCWO_LOG_DIR, log_dir, "status.json")
            with open(json_path) as f:
                status_dct = json.load(f)
                self.status = status_dct["status"]
                self.args = status_dct.get("args", [])
        except Exception as exc:
            self.status = "fail: " + str(exc)


    @property
    def log(self):
        log_path = os.path.join(settings.INCWO_LOG_DIR, self.log_dir, "details.log")
        if not os.path.exists(log_path):
            return "No log file"
        with open(log_path) as f:
            return f.read()


@pydici_feature("management")
def imports(request):
    if os.path.exists(settings.INCWO_LOG_DIR):
        log_dirs = os.listdir(settings.INCWO_LOG_DIR)
    else:
        log_dirs = []
    log_infos = [LogInfo(x) for x in log_dirs]
    log_infos.sort(key=lambda x: x.date, reverse=True)

    return render(request, "incwo/imports.html", {
        "log_infos": log_infos,
    })


@pydici_feature("management")
def details(request, log_dir):
    log_info = LogInfo(log_dir)
    return render(request, "incwo/details.html", {
        "log_info": log_info,
    })
