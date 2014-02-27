# coding: utf-8

"""
Helper module that factorize some code that would not be
appropriate to live in models or view
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

try:
    from pycarddav import carddav
    from pycarddav.model import vcard_from_string, vcard_from_vobject, get_names
    import vobject
    CARDDAV_ENABLE = True
except ImportError:
    CARDDAV_ENABLE = False


from django.db import IntegrityError

import pydici.settings


def connectToCardDavServer():
    """Connect to Card DAV server and return connection handler"""
    if pydici.settings.CARDDAV_SERVER and CARDDAV_ENABLE:
        server = carddav.PyCardDAV(pydici.settings.CARDDAV_SERVER,
                                   user=pydici.settings.CARDDAV_USER,
                                   passwd=pydici.settings.CARDDAV_PASSWD,
                                   verify=False,
                                   write_support=True)
        return server
    else:
        return None


def createOrUpdateContact(contact):
    """Create or update DAV contact from pydici contact
    @return; carddav url"""
    fname, lname = get_names(contact.name)
    vcard = vobject.vCard()
    for name, value, type_param in (("n", vobject.vcard.Name(family=lname, given=fname), None),
                                    ("fn", contact.name, None),
                                    ("email", contact.email, None),
                                    ("tel", contact.phone, "WORK"),
                                    ("tel", contact.mobile_phone, "CELL"),
                                    ("tel", contact.fax, "FAX"),
                                    ("title", contact.function, "None")):
        i = vcard.add(name)
        i.value = value
        if type_param:
            i.type_param = type_param

    card = vcard_from_vobject(vcard)
    server = connectToCardDavServer()
    if server:
        if contact.carddav:
            server.update_vcard(card.vcf.encode("utf-8"), contact.carddav, None)
            url = contact.carddav
        else:
            url, etag = server.upload_new_card(card.vcf)
        return url


def refreshContact():
    """Refresh local contact from remote DAV server"""
    from crm.models import Contact
    server = connectToCardDavServer()
    if not server:
        return
    for url in server.get_abook().keys():
        card = vcard_from_string(server.get_vcard(url))
        try:
            contact = Contact.objects.get(carddav=url)
        except Contact.DoesNotExist:
            contact = Contact()
            contact.carddav = url
        contact.name = card.fname
        contact.email = [i[0] for i in card["EMAIL"]][0]
        for number, prop in card["TEL"]:
            if "WORK" in prop.get("TYPE", ()):
                contact.phone = number
            if "CELL" in prop.get("TYPE", ()):
                contact.mobile_phone = number
            if "FAX" in prop.get("TYPE", ()):
                contact.fax = number
        try:
            contact.function = card["TITLE"][0][0]
        except IndexError:
            # No title defined.
            pass
        try:
            contact.save(remoteSave=False)
        except IntegrityError:
            print "Contact %s already exists - skipping" % contact.name
