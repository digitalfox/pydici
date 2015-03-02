import logging
import os

import requests
from lxml import objectify

from crm.models import Company, ClientOrganisation

logger = logging.getLogger('incwo')

SUB_DIRS = ('firms', 'contacts')

DEFAULT_CLIENT_ORGANIZATION_NAME = 'Default'


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
    words = name.split(' ')
    if len(words) >= 3:
        code = ''.join([x[0] for x in words])[:3]
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


def import_firms(firm_lst):
    count = len(firm_lst)
    for pos, (firm_id, firm_xml) in enumerate(firm_lst):
        firm = objectify.fromstring(firm_xml)
        name = unicode(firm.name)
        logger.info(' {}/{} {} ({})'.format(pos + 1, count, name.encode('utf-8'), firm_id))
        try:
            company = Company.objects.get(pk=firm_id)
        except Company.DoesNotExist:
            code = generate_unique_company_code(name)
            company = Company(pk=firm_id, name=name, code=code)
            company.save()

        co, created = ClientOrganisation.objects.get_or_create(name=DEFAULT_CLIENT_ORGANIZATION_NAME, company=company)
        co.save()


def load_objects(base_download_dir, sub_dir):
    lst = []
    download_dir = os.path.join(base_download_dir, sub_dir)
    for name in os.listdir(download_dir):
        obj_id = int(os.path.splitext(name)[0])
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
