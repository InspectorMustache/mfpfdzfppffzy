import os
import sys
import argparse
from . import views
from .client import ConnectClient
from .utils import KeyBindings, UserError, MPD_FIELDS

MFP_CUSTOM_CMDS = ('find', 'list')


class DynamicHeadersAction(argparse.Action):
    """Translate dynamic-headers selection into appropriate constant."""
    def __init__(self, *args, **kwargs):
        self.choice_dict = {
            'yes': views.DYNAMIC_HEADERS,
            'category': views.CAT_DYNAMIC_HEADERS,
            'no': views.NO_DYNAMIC_HEADERS}
        super().__init__(*args, **kwargs)

    def __call__(self, parser, namespace, value, *args, **kwargs):
        setattr(namespace, self.dest, self.choice_dict[value])


argparser = argparse.ArgumentParser()
argparser.add_argument('command', nargs='+')
argparser.add_argument('--mpd-host',
                       default=os.getenv('MPD_HOST') or '127.0.0.1',
                       help='address of a remote or local mpd server')
argparser.add_argument('--mpd-port',
                       type=int,
                       default=os.getenv('MPD_PORT') or '6600',
                       help='port address of a remote or local mpd server')
argparser.add_argument('--bind', help='keybindings in a comma-separated list')
argparser.add_argument('--sort', choices=MPD_FIELDS, metavar='MPD-TAG',
                       help='tag field to sort items by')
argparser.add_argument(
    '--the-strip', action='store_true',
    help='strip leading "The" of the sort field before sorting')
argparser.add_argument(
    '--dynamic-headers', choices=['yes', 'no', 'category'],
    default=views.NO_DYNAMIC_HEADERS, action=DynamicHeadersAction,
    help='create headers from the search query or the displayed tag fields')


def cat_str(cat, msg):
    """
    Return ansi-term string where cat precedes msg and is printed in bold.
    """
    return '\033[1m{}\033[0m:\n{}'.format(cat, msg)


def run_with_args(view_func, cmd, mpd_host=None, mpd_port=None, bind=None,
                  sort=None, the_strip=None, dynamic_headers=None):
    """Process arguments and call view_func."""
    mpc = ConnectClient(addr=mpd_host, port=mpd_port)
    mpc._listen_on_fifo()
    kb = KeyBindings(bind, fifo=mpc.fifo)
    view_settings = views.ViewSettings(
        cmd, keybinds=kb, dynamic_headers=dynamic_headers, sort_field=sort,
        the_strip=the_strip)

    view_func(mpc, view_settings)


def find(cmd, mpd_host, mpd_port, bind, sort, the_strip, dynamic_headers):
    """
    Display results from mpd's find command in a column based view. Each column
    correspond to the artist, album and title tags.

    \b
    Example queries:
    mfpfdzfppffzy find artist 'Jeff Rosenstock'
    mfpfdzfppffzy find artist 'Glocca Morra' album 'Just Married'
    """
    run_with_args(views.singles_view, cmd,
                  mpd_host=mpd_host, mpd_port=mpd_port, bind=bind,
                  sort=sort, the_strip=the_strip,
                  dynamic_headers=dynamic_headers)


def list(cmd, mpd_host, mpd_port, bind, sort, the_strip, dynamic_headers):
    """
    Display results from mpd's list command in a simple index view.

    \b
    Example queries:
    mfpfdzfppffzy list artist
    mfpfdzfppffzy list album artist Ampere
    """
    run_with_args(views.container_view, cmd,
                  mpd_host=mpd_host, mpd_port=mpd_port, bind=bind,
                  sort=sort, the_strip=the_strip,
                  dynamic_headers=dynamic_headers)


def parse_unregistered_command(ctx):
    """
    Try parsing a command that isn't registered as a click command as a regular
    mpd command by utilizing the commands click context.
    """
    raise NotImplementedError


def process_cli_args(cli_args):
    """Run application based on information gathered from the commandline."""
    try:
        raise NotImplementedError
    except UserError as e:
        print(cat_str('Error', str(e)))
        sys.exit(1)


if __name__ == '__main__':
    try:
        process_cli_args(argparser.parse_args())
    except KeyboardInterrupt:
        sys.exit(1)
