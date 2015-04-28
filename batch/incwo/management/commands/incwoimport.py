# -*- coding: UTF-8 -*-
"""
Management command to start imports from the command line
@author: Aurélien Gâteau (mail@agateau.com)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

import json
import logging
import os
import sys
from datetime import datetime
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from batch.incwo import utils

from crm.models import Subsidiary


sub_dirs_strings = ', '.join(['"' + x + '"' for x in utils.SUB_DIRS])


def read_ids(filename):
    with open(filename) as f:
        return set([int(x) for x in f.readlines()])


def make_allow_option(sub_dir):
    name = '--allow-' + sub_dir.replace('_', '-')
    return make_option(name, metavar='FILE',
                       help='Limit import of {} to those whose ids are listed '
                            'in FILE.'.format(sub_dir))


def make_deny_option(sub_dir):
    name = '--deny-' + sub_dir.replace('_', '-')
    return make_option(name, metavar='FILE',
                       help='Do not import {} whose ids are listed in FILE.'
                            .format(sub_dir))


class Status(object):
    def __init__(self, path, args):
        self.path = path
        self.status_dct = {
            'args': args
        }

    def update(self, status):
        self.status_dct['status'] = status
        with open(self.path, 'w') as f:
            json.dump(self.status_dct, f, indent=4)


class Command(BaseCommand):
    option_list = (
        make_option('--download',
                    help='Perform only the download step. WHAT must be either '
                         '"all", or a combination of {}, separated by commas.'
                         .format(sub_dirs_strings),
                    metavar='WHAT'),
        make_option('--import',
                    help='Perform only the import step. WHAT must be either '
                         '"all", or a combination of {}, separated by commas.'
                         .format(sub_dirs_strings),
                    metavar='WHAT'),
        make_option('--host',
                    help='Incwo host, for example https://www.incwo.com/123456'),
        make_option('-u', '--user',
                    help='Incwo username'),
        make_option('-p', '--password',
                    help='Incwo password'),
        make_option('-s', '--subsidiary',
                    help='ID of subsidiary to use for leads'),
        make_option('--missions', action='store_true',
                    help='Import missions in imported leads'),
        make_option('--ignore-errors', action='store_true',
                    help='Ignore errors instead of stopping. Errors are logged nevertheless.'),
    ) + tuple([make_allow_option(x) for x in utils.SUB_DIRS]) \
        + tuple([make_deny_option(x) for x in utils.SUB_DIRS]) \
        + BaseCommand.option_list

    args = '<download-dir>'
    help = """Import data from an Incwo account.

Import is done in two steps:
1. Downloading of the data from Incwo.
2. Import of the downloaded data in Pydici database.

The downloaded data is stored in <download-dir>.

By default the command will perform both steps, unless you specify the
--download or the --import option.

Options common to both steps:
--allow-*
--deny-*

Options specific to the download step:
--host
--user
--password

Note: Passing the credentials on the command line is not secure, they should be
kept in a .netrc file instead (see `man netrc`).

Options specific to the import step:
--subsidiary
--missions
--ignore-errors"""

    def handle(self, *args, **options):
        translation.activate(settings.LANGUAGE_CODE)
        if len(args) == 0:
            raise CommandError('Missing download dir argument')

        log_dir = self.setup_logging(options['verbosity'])

        status_path = os.path.join(log_dir, 'status.json')
        status = Status(status_path, sys.argv)
        status.update('running')
        try:
            download_dir = args[0]
            if options['import']:
                sub_dirs = self.parse_sub_dir_arg(options['import'])
                self.handle_import(download_dir, sub_dirs, options)
            elif options['download']:
                sub_dirs = self.parse_sub_dir_arg(options['download'])
                self.handle_download(download_dir, sub_dirs, options)
            else:
                # Do the whole thing
                self.handle_download(download_dir, utils.SUB_DIRS, options)
                self.handle_import(download_dir, utils.SUB_DIRS, options)
            status.update('success')
        except:
            status.update('failure')
            raise

    def setup_logging(self, verbosity):
        loglevels = {
            '0': logging.WARNING,
            '1': logging.INFO,
            '2': logging.DEBUG,
            '3': logging.DEBUG
        }
        loglevel = loglevels[verbosity]

        utils.logger.setLevel(loglevel)
        utils.logger.addHandler(logging.StreamHandler())

        name = datetime.now().isoformat().split('.')[0]
        log_dir = os.path.join(settings.INCWO_LOG_DIR, name)
        os.makedirs(log_dir)

        log_handler = logging.FileHandler(os.path.join(log_dir, 'details.log'), encoding='utf-8')
        utils.logger.addHandler(log_handler)

        return log_dir

    def handle_import(self, download_dir, sub_dirs, options):
        subsidiary_id = options['subsidiary']
        if subsidiary_id is None:
            raise CommandError('The --subsidiary option is missing')
        subsidiary = Subsidiary.objects.get(id=subsidiary_id)

        #TODO: use clientid to compose "id_prefix" to ensure its uniqueness among different incwo instances
        context = utils.ImportContext(ignore_errors=options['ignore_errors'],
                                      subsidiary=subsidiary,
                                      import_missions=options['missions'],
                                      id_prefix="incwo")

        for sub_dir in sub_dirs:
            name = 'allow_' + sub_dir
            if options[name]:
                context.allowed_ids_for_sub_dir[sub_dir] = read_ids(options[name])
            name = 'deny_' + sub_dir
            if options[name]:
                context.denied_ids_for_sub_dir[sub_dir] = read_ids(options[name])
            lst = utils.load_objects(download_dir, sub_dir)
            import_method = getattr(utils, 'import_' + sub_dir)
            import_method(lst, context)

    def handle_download(self, download_dir, sub_dirs, options):
        url = options['host']
        if options['user'] is not None:
            auth = options['user'], options['password']
        else:
            # Will fetch the user credentials from ~/.netrc
            auth = None
        for sub_dir in sub_dirs:
            name = 'allow_' + sub_dir
            if options[name]:
                allowed_ids = read_ids(options[name])
            else:
                allowed_ids = []
            name = 'deny_' + sub_dir
            if options[name]:
                denied_ids = read_ids(options[name])
            else:
                denied_ids = []
            objects = utils.download_objects(url, auth, sub_dir, allowed_ids, denied_ids)
            utils.save_objects(objects, download_dir, sub_dir)

    def parse_sub_dir_arg(self, arg):
        sub_dirs = arg.split(',')
        if sub_dirs == ['all']:
            sub_dirs = utils.SUB_DIRS
        else:
            for sub_dir in sub_dirs:
                if sub_dir not in utils.SUB_DIRS:
                    raise CommandError('Invalid subdir {}'.format(sub_dir))
        return sub_dirs
