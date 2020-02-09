# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in Crm models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from crm.models import Subsidiary


def get_subsidiary_from_request(request):
    """ Check if Retrieves a subsidiary by given id
    :param id: subsidiary_id
    :param request
    :return: found subsidiary otherwise none
    """

    if "subsidiary_id" in request.GET:
        return Subsidiary.objects.get(id=int(request.GET["subsidiary_id"]))
    return None
