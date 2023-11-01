# coding: utf-8
"""
Pydici people API.
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""
import logging

from django.http import JsonResponse
from django.db import transaction
from django.contrib.auth.models import User, Group

from core.decorator import pydici_non_public, pydici_feature
from people.models import Consultant, ConsultantProfile
from crm.models import Subsidiary


@pydici_non_public
@pydici_feature("reports")
def consultant_list(request):
    """Return json list of consultants"""
    data = Consultant.objects.all().values("name", "trigramme", "profil__name", "company__name", "subcontractor", "active", "productive")
    return JsonResponse(list(data), safe=False)


@pydici_non_public
def consultant_provisioning(request):
    """Create User and Consultant object"""
    try:
        if not request.user.is_superuser:
            raise Exception("Only superuser can create user")
        with transaction.atomic():
            user = User.objects.create_user(username=request.POST["trigramme"], password=request.POST["trigramme"])
            user.first_name = request.POST["firstname"]
            user.last_name = request.POST["lastname"]
            user.email = request.POST["email"]
            user.is_staff = False
            for group in request.POST.getlist("groups"):
                user.groups.add(Group.objects.get(name=group))
            user.save()

            consultant = Consultant(name="%s %s" % (request.POST["firstname"], request.POST["lastname"]),
                                    trigramme = request.POST["trigramme"].upper(),
                                    company = Subsidiary.objects.get(code=request.POST["company"],),
                                    profil = ConsultantProfile.objects.get(name=request.POST["profile"]))
            consultant.save()
            if request.headers.get("Dry-Run"):
                raise Exception("Dry-Run, rollback user creation")
        return JsonResponse({"result": "ok"})
    except Exception as e:
        logging.error(f"cannot create consultant: {e}")
        return JsonResponse({"result": "error", "msg": "exception occurs"})


@pydici_non_public
def consultant_deactivation(request):
    """Deactivate a consultant and remove according user"""
    try:
        if not request.user.is_superuser:
            raise Exception("Only superuser can deactivate user")
        with transaction.atomic():
            try:
                u = User.objects.get(username=request.POST["trigramme"])
                u.is_active = False
                u.is_staff = False
                u.is_superuser = False
                u.save()
            except User.DoesNotExist:
                pass
            consultant = Consultant.objects.get(trigramme=request.POST["trigramme"].upper())
            consultant.active = False
            consultant.save()
            if request.headers.get("Dry-Run"):
                return JsonResponse({"result": "nothing", "msg": "Dry run mode. Nothing was removed/deactivated"})
        return JsonResponse({"result": "ok"})
    except Exception as e:
        logging.error(f"cannot deactivate consultant: {e}")
        return JsonResponse({"result": "error", "msg": "exception occurs"})

