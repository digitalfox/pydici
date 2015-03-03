import logging

from optparse import make_option

from django.core.management.base import BaseCommand

from batch.incwo import core


sub_dirs_strings = ', '.join(['"' + x + '"' for x in core.SUB_DIRS])


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--download',
                    help='Download objects to download-dir, do not import anything. Values is a combination of {} separated by commas, or "all".'.format(sub_dirs_strings)),
        make_option('--host',
                    help='Incwo host'),
        make_option('-u', '--user',
                    help='Incwo username'),
        make_option('-p', '--password',
                    help='Incwo password'),
        make_option('--import', action='store_true',
                    help='Import downloaded data from download-dir, do not download anything'),
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

        download_dir = args[0]
        if options['import']:
            self.handle_import(download_dir, options)
        elif options['download']:
            self.handle_download(download_dir, options)
        else:
            # Do the whole thing
            self.handle_import(download_dir, options)
            self.handle_download(download_dir, options)

    def handle_import(self, download_dir, options):
        ignore_errors = options['ignore_errors']

        firms = core.load_objects(download_dir, 'firms')
        contacts = core.load_objects(download_dir, 'contacts')

        core.import_firms(firms, ignore_errors=ignore_errors)
        core.import_contacts(contacts, ignore_errors=ignore_errors)

    def handle_download(self, download_dir, options):
        url = options['host']
        auth = options['user'], options['password']
        sub_dirs = options['download'].split(',')
        if sub_dirs == ['all',]:
            sub_dirs = core.SUB_DIRS
        for sub_dir in sub_dirs:
            objects = core.download_objects(url, auth, sub_dir)
            core.save_objects(objects, download_dir, sub_dir)
