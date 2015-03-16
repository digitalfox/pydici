import logging

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from batch.incwo import core

from crm.models import Subsidiary


sub_dirs_strings = ', '.join(['"' + x + '"' for x in core.SUB_DIRS])


def read_ids(filename):
    with open(filename) as f:
        return set([int(x) for x in f.readlines()])


def make_limit_option(sub_dir):
    name = '--limit-' + sub_dir.replace('_', '-')
    return make_option(name, metavar='FILE',
                       help='Limit import of {} to those whose ids are listed in FILE'.format(sub_dir))


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--download',
                    help='Download objects to download-dir, do not import anything. Value is a combination of {} separated by commas, or "all".'.format(sub_dirs_strings)),
        make_option('--import',
                    help='Import downloaded data from download-dir, do not download anything. Value is a combination of {} separated by commas, or "all".'.format(sub_dirs_strings)),
        make_option('--host',
                    help='Incwo host'),
        make_option('-u', '--user',
                    help='Incwo username'),
        make_option('-p', '--password',
                    help='Incwo password'),
        make_option('-s', '--subsidiary',
                    help='ID of subsidiary to use for leads'),
        make_option('--missions', action='store_true',
                    help='Import missions in imported leads'),
        make_option('--ignore-errors', action='store_true',
                    help='Ignore errors instead of stopping. Errors are still logged though'),
    ) + tuple([make_limit_option(x) for x in core.SUB_DIRS])
    args = '<download-dir>'
    help = 'Import data from an Incwo account'

    def handle(self, *args, **options):
        translation.activate(settings.LANGUAGE_CODE)
        loglevels = {
            '0': logging.WARNING,
            '1': logging.INFO,
            '2': logging.DEBUG,
            '3': logging.DEBUG
        }
        loglevel = loglevels[options['verbosity']]
        core.logger.setLevel(loglevel)
        core.logger.addHandler(logging.StreamHandler())

        if len(args) == 0:
            raise CommandError('Missing download dir argument')
        download_dir = args[0]
        if options['import']:
            sub_dirs = self.parse_sub_dir_arg(options['import'])
            self.handle_import(download_dir, sub_dirs, options)
        elif options['download']:
            sub_dirs = self.parse_sub_dir_arg(options['import'])
            self.handle_download(download_dir, sub_dirs, options)
        else:
            # Do the whole thing
            self.handle_download(download_dir, core.SUB_DIRS, options)
            self.handle_import(download_dir, core.SUB_DIRS, options)

    def handle_import(self, download_dir, sub_dirs, options):
        subsidiary_id = options['subsidiary']
        if subsidiary_id is None:
            raise CommandError('The --subsidiary option is missing')
        subsidiary = Subsidiary.objects.get(id=subsidiary_id)

        context = core.ImportContext(ignore_errors=options['ignore_errors'],
                                     subsidiary=subsidiary,
                                     import_missions=options['missions'])

        for sub_dir in sub_dirs:
            name = 'limit_' + sub_dir
            if options[name]:
                context.id_limit_for_sub_dir[sub_dir] = read_ids(options[name])
            lst = core.load_objects(download_dir, sub_dir)
            import_method = getattr(core, 'import_' + sub_dir)
            import_method(lst, context)

    def handle_download(self, download_dir, sub_dirs, options):
        url = options['host']
        auth = options['user'], options['password']
        for sub_dir in sub_dirs:
            objects = core.download_objects(url, auth, sub_dir)
            core.save_objects(objects, download_dir, sub_dir)

    def parse_sub_dir_arg(self, arg):
        sub_dirs = arg.split(',')
        if sub_dirs == ['all',]:
            sub_dirs = core.SUB_DIRS
        else:
            for sub_dir in sub_dirs:
                if not sub_dir in core.SUB_DIRS:
                    raise CommandError('Invalid subdir {}'.format(sub_dir))
        return sub_dirs
