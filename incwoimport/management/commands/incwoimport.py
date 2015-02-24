import os
from optparse import make_option

import requests
from lxml import objectify

from django.core.management.base import BaseCommand

from crm.models import Company, ClientOrganisation

SUB_DIRS = ('firms', 'contacts')

DEFAULT_CLIENT_ORGANIZATION_NAME = 'Default'


def generate_unique_company_code(name):
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


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('-u', '--user',
                    help='Incwo username'),
        make_option('-p', '--password',
                    help='Incwo password'),
        make_option('-d', '--download',
                    help='Download data to DIR, do not import anything',
                    metavar='DIR'),
        make_option('-i', '--import',
                    help='Import downloaded data from DIR, do not download anything',
                    metavar='DIR'),
    )
    args = '<server_url>'
    help = 'Import data from an Incwo account'

    def handle(self, *args, **options):
        if options['import']:
            # Load already-downloaded objects
            firms = self.load_objects(options['import'], 'firms')
        else:
            # Download objects
            url = args[0]
            auth = options['user'], options['password']
            for sub_dir in SUB_DIRS:
                objects = self.download_objects(url, auth, sub_dir)
                if options['download']:
                    self.save_objects(objects, options['download'], sub_dir)
            if options['download']:
                return

        self.import_firms(firms)

    def download_objects(self, base_url, auth, sub_dir, page=1):
        """
        Download XML files for all objects
        Returns a dict of obj_id => obj_as_xml_string
        """
        url = '{}/{}.xml'.format(base_url, sub_dir)
        self.stdout.write('Downloading {} page={}'.format(url, page))
        res = requests.get(url, auth=auth, params={'page': page})
        root = objectify.fromstring(res.content)

        dct= {}
        for obj_element in root.iterchildren():
            if obj_element.tag == 'pagination':
                continue
            obj_id = obj_element.id
            url = '{}/{}/{}.xml'.format(base_url, sub_dir, obj_id)
            self.stdout.write('Downloading ' + url)
            res = requests.get(url, auth=auth)
            dct[obj_id] = res.text

        total_pages = root.pagination.total_pages
        if page < total_pages:
            dct.update(self.download_objects(base_url, auth, sub_dir, page=page + 1))
        return dct

    def import_firms(self, firm_dct):
        for firm_id, firm_xml in firm_dct.items():
            firm = objectify.fromstring(firm_xml)
            try:
                company = Company.objects.get(pk=firm_id)
            except Company.DoesNotExist:
                code = generate_unique_company_code(unicode(firm.name))
                company = Company(pk=firm_id, name=unicode(firm.name), code=code)
                company.save()

            co, created = ClientOrganisation.objects.get_or_create(name=DEFAULT_CLIENT_ORGANIZATION_NAME, company=company)
            co.save()

    def load_objects(self, base_download_dir, sub_dir):
        dct = {}
        download_dir = os.path.join(base_download_dir, sub_dir)
        for name in os.listdir(download_dir):
            obj_id = int(os.path.splitext(name)[0])
            xml_filename = os.path.join(download_dir, name)
            with open(xml_filename) as f:
                obj_xml = f.read()
            dct[obj_id] = obj_xml
        return dct

    def save_objects(self, obj_dct, base_download_dir, sub_dir):
        download_dir = os.path.join(base_download_dir, sub_dir)
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        for obj_id, obj_xml in obj_dct.items():
            xml_filename = os.path.join(download_dir, str(obj_id) + '.xml')
            with open(xml_filename, 'w') as f:
                f.write(obj_xml)
