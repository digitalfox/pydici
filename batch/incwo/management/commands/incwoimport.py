import logging

from optparse import make_option

from django.core.management.base import BaseCommand

from batch.incwo import core


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
        loglevels = {
            '0': logging.WARNING,
            '1': logging.INFO,
            '2': logging.DEBUG,
            '3': logging.DEBUG
        }
        loglevel = loglevels[options['verbosity']]
        core.logger.setLevel(loglevel)
        core.logger.addHandler(logging.StreamHandler())

        if options['import']:
            # Load already-downloaded objects
            firms = core.load_objects(options['import'], 'firms')
        else:
            # Download objects
            url = args[0]
            auth = options['user'], options['password']
            for sub_dir in core.SUB_DIRS:
                objects = core.download_objects(url, auth, sub_dir)
                if options['download']:
                    core.save_objects(objects, options['download'], sub_dir)
            if options['download']:
                return

        core.import_firms(firms)
