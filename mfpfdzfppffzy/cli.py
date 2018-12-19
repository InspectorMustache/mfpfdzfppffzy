import os
import sys
import argparse
from functools import partial
from collections import defaultdict
from . import views
from .client import ConnectClient
from .bind import KeyBindings
from .utils import UserError, MPD_FIELDS


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


def print_with_category(cat, msg):
    """
    Return ansi-term string where cat precedes msg and is printed in bold.
    """
    return '\033[1m{}\033[0m:\n{}'.format(cat, msg)


def run_with_args(view_func, mpc, cli_args):
    """Run view_func with the processed cli_args."""
    mpc.listen_on_fifo()
    kb = KeyBindings(cli_args.bind, fifo=mpc.fifo)
    view_settings = views.ViewSettings(
        cli_args.command, keybinds=kb,
        dynamic_headers=cli_args.dynamic_headers,
        sort_field=cli_args.sort, the_strip=cli_args.the_strip)

    view_func(mpc, view_settings)


def mpd_list_to_str(find_list):
    """Create a string representation list of a find_list."""
    try:
        # if it's a list of dicts process each individually into a string
        str_list = []
        for d in (x.items() for x in find_list):
            str_list.append('\n'.join(':\n'.join(y) for y in d))

        return '\n\n'.join(str_list)
    except AttributeError:
        # otherwise just process it as a list of strings
        return '\n'.join(find_list)


def find_dict_to_str(find_dict):
    """Create a string representation list of a find_dict."""
    str_list = [':\n'.join(x) for x in find_dict.items()]
    return '\n'.join(str_list)


def run_as_mpd_command(mpc, cli_args):
    """
    Take a command from the cli and try running it as a regular mpd command.
    """
    mpd_return = mpc.run_mpd_command(cli_args.command)
    print_mpd_return(mpd_return)


def print_mpd_return(mpd_return):
    """Handle and print the return value of an mpd command."""
    try:
        if type(mpd_return) is dict:
            mpd_return = find_dict_to_str(mpd_return)
        elif type(mpd_return) is list:
            mpd_return = mpd_list_to_str(mpd_return)
        else:
            mpd_return = '\n'.join(mpd_return)
    except TypeError:
        pass

    if mpd_return:
        print(mpd_return)


def process_cli_args(cli_args):
    """Run application based on information gathered from the commandline."""
    mpc = ConnectClient(cli_args.mpd_host, port=cli_args.mpd_port)
    base_cmd = cli_args.command[0]

    if not cli_args.bare:
        mfp_cmds[base_cmd](mpc, cli_args)
    else:
        run_as_mpd_command(mpc, cli_args)


# dict that selects the appropriate function:
# either run_with_args with the appropriate view or run_as_mpd_command as a
# fallback
mfp_cmds = defaultdict(lambda: run_as_mpd_command)
mfp_cmds.update({'find': partial(run_with_args, views.singles_view),
                 'search': partial(run_with_args, views.singles_view),
                 'list': partial(run_with_args, views.container_view)})

if __name__ == '__main__':
    try:
        process_cli_args(argparser.parse_args())
    except UserError as e:
        print(print_with_category('Error', str(e)))
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
