# encoding: utf-8
import logging
import os
import re
from datetime import datetime
from decimal import Decimal

import requests
from lxml import objectify

from django.utils.formats import localize

from crm.models import Company, ClientOrganisation, Client, Contact
from leads.models import Lead
from staffing.models import Mission

import dbutils


logger = logging.getLogger('incwo')

SUB_DIRS = ('firms', 'contacts', 'proposal_sheets')

DEFAULT_CLIENT_ORGANIZATION_NAME = 'Default'


OPTIONAL_MISSION_SUFFIX = '_[option]_'


class IncwoImportError(Exception):
    pass


class ImportContext(object):
    def __init__(self, ignore_errors=False,
                 subsidiary=None,
                 import_missions=False):
        self.ignore_errors = ignore_errors
        self.subsidiary = subsidiary
        self.import_missions = import_missions
        self.allowed_ids_for_sub_dir = {}
        self.denied_ids_for_sub_dir = {}


def _parse_incwo_date(txt):
    return datetime.strptime(txt, '%d-%m-%Y')


def is_id_allowed(obj_id, allowed_ids, denied_ids):
    if allowed_ids and obj_id not in allowed_ids:
        return False
    if denied_ids and obj_id in denied_ids:
        return False
    return True


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
    words = re.split(r'\W', name)
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


def download_objects(base_url, auth, sub_dir, allowed_ids, denied_ids, page=1):
    """
    Download XML files for all objects
    Returns a list of tuples (obj_id, obj_as_xml_string)
    """
    url = '{}/{}.xml'.format(base_url, sub_dir)
    logger.info('Downloading %s page=%d', url, page)
    res = requests.get(url, auth=auth, params={'page': page})
    if res.status_code != 200:
        raise IncwoImportError(res.content)
    root = objectify.fromstring(res.content)

    lst = []
    for obj_element in root.iterchildren():
        if obj_element.tag == 'pagination':
            continue
        obj_id = obj_element.id
        if not is_id_allowed(obj_id, allowed_ids, denied_ids):
            continue
        url = '{}/{}/{}.xml'.format(base_url, sub_dir, obj_id)
        logger.info('Downloading %s', url)
        res = requests.get(url, auth=auth)
        if res.status_code != 200:
            raise IncwoImportError(res.content)
        lst.append((obj_id, res.text))

    total_pages = root.pagination.total_pages
    if page < total_pages:
        lst.extend(download_objects(base_url, auth, sub_dir, allowed_ids, denied_ids, page=page + 1))
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
    allowed_ids = context.allowed_ids_for_sub_dir.get(sub_dir)
    denied_ids = context.denied_ids_for_sub_dir.get(sub_dir)
    for pos, (obj_id, obj_xml) in enumerate(lst):
        if not is_id_allowed(obj_id, allowed_ids, denied_ids):
            continue
        filename = os.path.join(sub_dir, str(obj_id) + '.xml')
        logger.info('Importing %s (%d/%d)', filename, pos + 1, count)
        try:
            import_fcn(obj_id, obj_xml, context)
        except Exception:
            if context.ignore_errors:
                logger.exception('Failed to import %s', filename)
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
    dbutils.get_list_or_create(Client, organisation=co)


def import_firms(lst, context=None):
    if context is None:
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
    db_contact, _ = dbutils.update_or_create(Contact, id=contact.id, name=name)

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
    if context is None:
        context = ImportContext()
    _do_import('contacts', lst, import_contact, context)


class ProposalLineContext(object):
    def __init__(self):
        self._groups = [Decimal(0)]

    def add_to_current_total(self, price):
        self._groups[-1] += price

    def start_group(self):
        self._groups.append(Decimal(0))

    def current_total(self):
        return self._groups[-1]

    def grand_total(self):
        return sum(self._groups)


def simplify_decimal(value):
    # Convert to int if possible to ensure Decimal(2) is turned into '2', not
    # '2.0'
    int_value = value.to_integral_value()
    return int_value if int_value == value else value


def import_proposal_line(line, context):
    content_kind = unicode(line.content_kind)

    if content_kind == '' and not hasattr(line, 'total_price'):
        content_kind = 'comment'

    if hasattr(line, 'description_more'):
        description_more = unicode(line.description_more).strip()
    else:
        description_more = ''

    if content_kind == 'total':
        total = context.current_total()
        description = u'Total: {} €\n'.format(localize(total))
        context.start_group()

    elif content_kind == 'comment':
        description = unicode(line.description).strip()
        if description:
            description = '*' + description + '*'
        if description_more:
            description += '\n' + description_more

    else:
        # Normal lines + options
        description = unicode(line.description).strip()
        description = '- ' + description
        if content_kind == 'option':
            description += ' ' + OPTIONAL_MISSION_SUFFIX
        if description_more:
            description += '. ' + description_more

        if hasattr(line, 'unit_price') and hasattr(line, 'quantity'):
            # This is a product proposal line with an attached price
            unit_price = Decimal(unicode(line.unit_price))
            unit_price = simplify_decimal(unit_price)

            unit = unicode(line.unit)
            if unit:
                unit = ' ' + unit

            quantity = Decimal(unicode(line.quantity))
            quantity = simplify_decimal(quantity)

            # Do not use line.total_price: it is set to 0 for options
            total_price = unit_price * quantity

            description += '. '
            if quantity == 1:
                description += u'{} €'.format(localize(total_price))
            else:
                description += u'{}{} × {} € = {} €'.format(
                    quantity,
                    unit,
                    localize(unit_price),
                    localize(total_price))

            if not content_kind == 'option':
                context.add_to_current_total(total_price)

    return description


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
        logger.warning('Skipping proposal sheet %d: sheet_type is %s', obj_id, sheet.sheet_type)
        return

    state = STATE_FOR_PROGRESS_ID[sheet.progress_id]
    if state != 'WON':
        logger.warning('Skipping proposal sheet %d: not won', obj_id)
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

    lead, _ = dbutils.update_or_create(Lead,
                                       id=sheet.id,
                                       name=name,
                                       client=client,
                                       subsidiary=context.subsidiary,
                                       state=state,
                                       creation_date=_parse_incwo_date(unicode(sheet.billing_date)),
                                       description=unicode(sheet.subtitle).strip(),
                                       deal_id=unicode(sheet.reference).strip())

    if hasattr(sheet, 'proposal_lines') and context.import_missions:
        lst = list(sheet.proposal_lines.iterchildren())
        proposal_line_context = ProposalLineContext()
        lines = []
        if lead.description:
            lines.append(lead.description)
        for pos, proposal_line in enumerate(lst):
            logger.info('- Proposal line %d/%d', pos + 1, len(lst))
            lines.append(import_proposal_line(proposal_line, proposal_line_context))
        lead.description = '\n'.join(lines)
        lead.sales = proposal_line_context.grand_total() / 1000  # grand_total is in €, but lead.sales is in k€
        lead.save()

        dbutils.update_or_create(Mission,
                                 id=lead.id,
                                 lead=lead,
                                 subsidiary=lead.subsidiary,
                                 billing_mode='FIXED_PRICE',
                                 price=lead.sales)


def import_proposal_sheets(lst, context=None):
    if context is None:
        context = ImportContext()
    _do_import('proposal_sheets', lst, import_proposal_sheet, context)
