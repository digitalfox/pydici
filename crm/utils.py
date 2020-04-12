# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Crm models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from crm.models import Subsidiary


def get_subsidiary_from_request(request):
    """ Check if was given in URL and returns it
    :param id: subsidiary_id
    :param request
    :return: found subsidiary otherwise none
    """
    if "subsidiary_id" in request.GET:
        subsidiary_id = int(request.GET["subsidiary_id"])
        if subsidiary_id > 0:  # 0 mean all subsidiaries
            return Subsidiary.objects.get(id=subsidiary_id)


def get_subsidiary_from_session(request):
    """ Returns current subsidiary or None if not defined or scope is all"""
    current_subsidiary = None
    if "subsidiary_id" in request.session:
        if request.session["subsidiary_id"] > 0:  # 0 mean all subsidiaries
            current_subsidiary = Subsidiary.objects.get(id=request.session["subsidiary_id"])
    return current_subsidiary
