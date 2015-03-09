# encoding: utf-8
import logging
import os
import re
from datetime import datetime

import requests
from lxml import objectify

from crm.models import Company, ClientOrganisation, Client, Contact
from leads.models import Lead
from staffing.models import Mission

logger = logging.getLogger('incwo')

SUB_DIRS = ('firms', 'contacts', 'proposal_sheets')

DEFAULT_CLIENT_ORGANIZATION_NAME = 'Default'


class IncwoImportError(Exception):
    pass


class ImportContext(object):
    def __init__(self, ignore_errors=False,
                 subsidiary=None,
                 import_missions=False):
        self.ignore_errors = ignore_errors
        self.subsidiary = subsidiary
        self.import_missions = import_missions


def _parse_incwo_date(txt):
    return datetime.strptime(txt, '%d-%m-%Y')


def _get_list_or_create(model, **kwargs):
    """
    Create an object using kwargs if no objects match them. Similar to
    get_or_create, but does not fail if more than one object exists.

    If objects matched, returns a tuple of (object list, False)
    If no object matched, returns a tuple of ([new object], True)
    """
    lst = model.objects.filter(**kwargs)
    if lst:
        return lst, False
    obj = model(**kwargs)
    obj.save()
    return [obj], True


def generate_unique_company_code(name):
    """
    Try to generate a reasonable company 3 letter code
    - If the name is made of 3 words or more, use the initial of the first 3
      words
    - If the name is made of 2 words, use the initial of the first word and the
      first 2 letters of the second word
    - If the name is made of one word, use the first 3 letters

    Once done, iterate on existing codes and solve conflicts by replacing the
    last letter with an incrementing digit
    """
    words = re.split('\W', name)
    if len(words) >= 3:
        code = ''.join([x[0] for x in words if x])[:3]
    elif len(words) == 2:
        code = words[0][0] + words[1][:2]
    else:
        code = name[:3]
    code = code.upper()

    idx = 1
    base_code = code
    while True:
        try:
            Company.objects.get(code=code)
        except Company.DoesNotExist:
            return code
        # Let's hope there is no more than 10 clashes for now
        code = base_code[:2] + str(idx)
        idx += 1


def download_objects(base_url, auth, sub_dir, page=1):
    """
    Download XML files for all objects
    Returns a list of tuples (obj_id, obj_as_xml_string)
    """
    url = '{}/{}.xml'.format(base_url, sub_dir)
    logger.info('Downloading {} page={}'.format(url, page))
    res = requests.get(url, auth=auth, params={'page': page})
    root = objectify.fromstring(res.content)

    lst = []
    for obj_element in root.iterchildren():
        if obj_element.tag == 'pagination':
            continue
        obj_id = obj_element.id
        url = '{}/{}/{}.xml'.format(base_url, sub_dir, obj_id)
        logger.info('Downloading ' + url)
        res = requests.get(url, auth=auth)
        lst.append((obj_id, res.text))

    total_pages = root.pagination.total_pages
    if page < total_pages:
        lst.extend(download_objects(base_url, auth, sub_dir, page=page + 1))
    lst.sort(key=lambda x: x[0])
    return lst


def load_objects(base_download_dir, sub_dir):
    lst = []
    download_dir = os.path.join(base_download_dir, sub_dir)
    for name in os.listdir(download_dir):
        id_str, ext = os.path.splitext(name)
        if ext != '.xml':
            # Skip files like Vim swap files
            continue
        obj_id = int(id_str)
        xml_filename = os.path.join(download_dir, name)
        with open(xml_filename) as f:
            obj_xml = f.read()
        lst.append((obj_id, obj_xml))
    lst.sort(key=lambda x: x[0])
    return lst


def save_objects(obj_lst, base_download_dir, sub_dir):
    download_dir = os.path.join(base_download_dir, sub_dir)
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    for obj_id, obj_xml in obj_lst:
        xml_filename = os.path.join(download_dir, str(obj_id) + '.xml')
        with open(xml_filename, 'w') as f:
            f.write(obj_xml)


def _do_import(sub_dir, lst, import_fcn, context):
    count = len(lst)
    for pos, (obj_id, obj_xml) in enumerate(lst):
        filename = os.path.join(sub_dir, str(obj_id) + '.xml')
        logger.info('Importing {} ({}/{})'.format(filename, pos + 1, count))
        try:
            import_fcn(obj_id, obj_xml, context)
        except Exception:
            if context.ignore_errors:
                logger.exception('Failed to import {}'.format(filename))
            else:
                raise


def import_firm(obj_id, obj_xml, context):
    firm = objectify.fromstring(obj_xml)
    name = unicode(firm.name)

    try:
        company = Company.objects.get(pk=obj_id)
    except Company.DoesNotExist:
        # If there is a company with the same name already, generate a
        # unique name
        idx = 1
        basename = name + '-'
        while True:
            try:
                Company.objects.get(name=name)
            except Company.DoesNotExist:
                break
            name = basename + str(idx)
            idx += 1

        # Create the company entry
        code = generate_unique_company_code(name)
        company = Company(pk=obj_id, name=name, code=code)
        company.save()

    co, _ = ClientOrganisation.objects.get_or_create(name=DEFAULT_CLIENT_ORGANIZATION_NAME, company=company)
    _get_list_or_create(Client, organisation=co)


def import_firms(lst, context=None):
    if context == None:
        context = ImportContext()
    _do_import('firms', lst, import_firm, context)


# This list maps a field name in the Contact table with Incwo contact type
# ids, in order of preference
CONTACT_TYPE_MAPPING = {
    'phone': [
        471,  # main professional phone
        24,  # professional phone
        23,  # personal phone
    ],
    'mobile_phone': [
        88,  # professional cell phone
        554,  # personal cell phone
    ],
    'fax': [
        26,  # professional fax
        25,  # personal fax
    ],
    'email': [
        27,  # professional email
        28,  # personal email
    ]
}
# Unsupported for now
#     430,  # Skype address
#     431,  # Yahoo messenger id
#     432,  # MSN messenger id
#     433,  # AIM messenger id
#     457,  # ICQ messenger id

def import_contact_items(db_contact, items):
    dct = dict((x.type_id, x.value) for x in items.iterchildren())

    # For each field, look for the best available contact entry if any and use
    # it
    for field, type_id_lst in CONTACT_TYPE_MAPPING.items():
        for type_id in type_id_lst:
            value = dct.get(type_id)
            if value:
                setattr(db_contact, field, value)
                break


def import_contact(obj_id, obj_xml, context):
    contact = objectify.fromstring(obj_xml)
    # Note: There is a 'first_last_name' field, but it's not documented, so
    # better ignore it
    name = unicode(contact.first_name) + ' ' + unicode(contact.last_name)
    db_contact, _ = Contact.objects.get_or_create(id=contact.id, name=name)

    if hasattr(contact, 'job_title'):
        db_contact.function = unicode(contact.job_title)

    if hasattr(contact, 'contact_items'):
        import_contact_items(db_contact, contact.contact_items)

    db_contact.save()

    if hasattr(contact, 'firm_id'):
        organisation = ClientOrganisation.objects.get(company_id=contact.firm_id,
                                                      name=DEFAULT_CLIENT_ORGANIZATION_NAME)
        Client.objects.get_or_create(contact=db_contact, organisation=organisation)


def import_contacts(lst, context=None):
    if context == None:
        context = ImportContext()
    _do_import('contacts', lst, import_contact, context)


def import_proposal_line(lead, line):
    mission, _ = Mission.objects.get_or_create(id=line.id,
                                               lead=lead,
                                               subsidiary=lead.subsidiary)
    mission.description = unicode(line.description).strip()
    if hasattr(line, 'description_more'):
        mission.description += ' - ' + unicode(line.description_more).strip()
    mission.billing_mode = 'FIXED_PRICE'
    # FIXME: Compute probability from lead state?
    # FIXME: Which price to use for mission.price: line.total_price or
    # line.total_price_with_taxes?
    mission.price = float(line.total_price_with_taxes) / 1000
    mission.save()


# FIXME: Is 'WON' the right value for 'Terminé'?
STATE_FOR_PROGRESS_ID = {
    555:    'WRITE_OFFER',  # En rédaction
    556:    'OFFER_SENT',   # Envoyé au client
    557:    'WON',          # Accepté
    558:    'LOST',         # Refusé
    559:    'SLEEPING',     # Ajourné
    620105: 'WON',          # Terminé
}

def import_proposal_sheet(obj_id, obj_xml, context):
    sheet = objectify.fromstring(obj_xml)
    if sheet.sheet_type != 'proposal':
        logger.warning('Skipping proposal sheet {}: sheet_type is {}'.format(obj_id, sheet.sheet_type))
        return

    state = STATE_FOR_PROGRESS_ID[sheet.progress_id]
    if state != 'WON':
        logger.warning('Skipping proposal sheet {}: not won'.format(obj_id))
        return

    firm_id = sheet.firm_id if hasattr(sheet, 'firm_id') else 0
    contact_id = sheet.contact_id if hasattr(sheet, 'contact_id') else 0
    if firm_id == 0 and contact_id == 0:
        raise IncwoImportError('Invalid proposal sheet {}: neither firm_id nor contact_id are set'.format(obj_id))

    name = unicode(sheet.title).strip()

    if contact_id > 0:
        # Find client from contact, use the default organisation
        client = Client.objects.get(contact_id=sheet.contact_id,
                                    organisation__name=DEFAULT_CLIENT_ORGANIZATION_NAME)
    else:
        # Find client from company, use the default organisation and the
        # default, contact-less, client
        client = Client.objects.get(organisation__company_id=sheet.firm_id,
                                    organisation__name=DEFAULT_CLIENT_ORGANIZATION_NAME,
                                    contact=None)

    try:
        lead = Lead.objects.get(id=sheet.id)
        lead.name = name
        lead.client = client
        lead.subsidiary = context.subsidiary
    except Lead.DoesNotExist:
        lead = Lead(id=sheet.id, name=name, client=client, subsidiary=context.subsidiary)

    lead.state = state
    lead.creation_date = _parse_incwo_date(unicode(sheet.billing_date))
    lead.description = unicode(sheet.subtitle).strip()
    lead.deal_id = unicode(sheet.reference).strip()
    lead.save()

    if hasattr(sheet, 'proposal_lines') and context.import_missions:
        lst = list(sheet.proposal_lines.iterchildren())
        for pos, proposal_line in enumerate(lst):
            logger.info('- Proposal line {}/{}'.format(pos + 1, len(lst)))
            import_proposal_line(lead, proposal_line)


def import_proposal_sheets(lst, context=None):
    if context == None:
        context = ImportContext()
    _do_import('proposal_sheets', lst, import_proposal_sheet, context)
