import os
import sys
import argparse
from . import views
from .client import ConnectClient
from .utils import KeyBindings, UserError, MPD_FIELDS

# commands that are specified by mfpfdzfppffzy and the view functions they are
# associated with
mfp_custom_cmds = {'find': views.singles_view,
                   'list': views.container_view}


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
argparser.add_argument('command', nargs='+', metavar='CMD',
                       help='an mpd command')
argparser.add_argument('--mpd-host',
                       default=os.getenv('MPD_HOST') or '127.0.0.1',
                       help='address of a remote or local mpd server')
argparser.add_argument('--mpd-port',
                       type=int,
                       default=os.getenv('MPD_PORT') or '6600',
                       help='port address of a remote or local mpd server')
argparser.add_argument('--bare', action='store_true',
                       help='simply pass command to mpd and return the result')
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


def run_with_args(mpc, view_func, cli_args):
    """Run view_func with the processed cli_args."""
    mpc._listen_on_fifo()
    kb = KeyBindings(cli_args.bind, fifo=mpc.fifo)
    view_settings = views.ViewSettings(
        cli_args.command[1:], keybinds=kb,
        dynamic_headers=cli_args.dynamic_headers,
        sort_field=cli_args.sort, the_strip=cli_args.the_strip)

    view_func(mpc, view_settings)


def find_list_to_str(find_list):
    """Create a string representation list of a find_list."""
    str_list = []
    for d in (x.items() for x in find_list):
        str_list.extend(':\n'.join(y) for y in d)

    return str_list


def find_dict_to_str(find_dict):
    """Create a string representation list of a find_dict."""
    return [':\n'.join(x) for x in find_dict.items()]


def print_mpd_return(mpd_return):
    """Handle and print the return value of an mpd command."""
    try:
        if type(mpd_return) is dict:
            mpd_return = find_dict_to_str(mpd_return)
        elif type(mpd_return[0]) is dict:
            mpd_return = find_list_to_str(mpd_return)

        mpd_return = '\n'.join(mpd_return)
    except TypeError:
        pass

    if mpd_return:
        print(mpd_return)


def process_cli_args(cli_args):
    """Run application based on information gathered from the commandline."""
    mpc = ConnectClient(cli_args.mpd_host, port=cli_args.mpd_port)
    base_cmd = cli_args.command[0]

    if not cli_args.bare and base_cmd in mfp_custom_cmds.keys():
        run_with_args(mpc, mfp_custom_cmds[base_cmd], cli_args)
    else:
        mpd_return = mpc.mfp_run_command(' '.join(cli_args.command))
        print_mpd_return(mpd_return)


if __name__ == '__main__':
    try:
        process_cli_args(argparser.parse_args())
    except UserError as e:
        print(cat_str('Error', str(e)))
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
