import logging

from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from batch.incwo import core

from crm.models import Subsidiary


sub_dirs_strings = ', '.join(['"' + x + '"' for x in core.SUB_DIRS])


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--download',
                    help='Download objects to download-dir, do not import anything. Value is a combination of {} separated by commas, or "all".'.format(sub_dirs_strings)),
        make_option('--host',
                    help='Incwo host'),
        make_option('-u', '--user',
                    help='Incwo username'),
        make_option('-p', '--password',
                    help='Incwo password'),
        make_option('-s', '--subsidiary',
                    help='ID of subsidiary to use for leads'),
        make_option('--import',
                    help='Import downloaded data from download-dir, do not download anything. Value is a combination of {} separated by commas, or "all".'.format(sub_dirs_strings)),
        make_option('--ignore-errors', action='store_true',
                    help='Ignore errors instead of stopping. Errors are still logged though'),
    )
    args = '<download-dir>'
    help = 'Import data from an Incwo account'

    def handle(self, *args, **options):
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
            self.handle_import(download_dir, core.SUB_DIRS, options)
            self.handle_download(download_dir, core.SUB_DIRS, options)

    def handle_import(self, download_dir, sub_dirs, options):
        ignore_errors = options['ignore_errors']
        subsidiary_id = options['subsidiary']
        if subsidiary_id is None:
            raise CommandError('The --subsidiary option is missing')
        subsidiary = Subsidiary.objects.get(id=subsidiary_id)

        kwargs = {
            'subsidiary': subsidiary,
            'ignore_errors': ignore_errors
        }
        for sub_dir in sub_dirs:
            lst = core.load_objects(download_dir, sub_dir)
            import_method = getattr(core, 'import_' + sub_dir)
            import_method(lst, **kwargs)

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
