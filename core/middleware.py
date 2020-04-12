# -*- coding: UTF-8 -*-
"""
Pydici core middleware
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""


class ScopeMiddleware:
    """Catch scope change request and update session accordingly"""
    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):
        if "subsidiary_id" in request.GET:
            try:
                subsidiary_id = int(request.GET["subsidiary_id"])
            except ValueError:
                subsidiary_id = 0
            request.session["subsidiary_id"] = subsidiary_id
        return self.get_response(request)
