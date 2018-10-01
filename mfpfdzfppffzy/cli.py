import click
from . import views
from .client import ConnectClient
from .utils import KeyBindings, MPD_FIELDS

generic_options_list = [
    click.argument('cmd', nargs=-1, metavar='QUERY', required=True),
    click.option('--mpd-host', envvar='MPD_HOST', default='127.0.0.1',
                 help='address of a remote or local mpd server'),
    click.option('--mpd-port', envvar='MPD_PORT', default=6600,
                 help='port address of a remote or local mpd server'),
    click.option('--bind',
                 help='keybindings in a comma-separated list'),
    click.option('--sort', type=click.Choice(MPD_FIELDS),
                 help='tag field to sort items by')]


def translate_dynamic_headers(choice):
    """
    Translate choice from the dynamic_headers argument to a value that can be
    passed as the dynamic_headers argument of a ViewSettings object.
    """
    if choice == 'yes':
        return views.DYNAMIC_HEADERS
    elif choice == 'category':
        return views.CAT_DYNAMIC_HEADERS
    else:
        return views.NO_DYNAMIC_HEADERS


def generic_options(func):
    """Bundle some click options into a single decorator."""
    for option in reversed(generic_options_list):
        func = option(func)
    return func


@click.group()
def mfpfdzfppffzy():
    """Browse the mpd library with fzf."""
    pass


def run_with_args(view_func, cmd, mpd_host=None, mpd_port=None, bind=None,
                  sort=None, dynamic_headers=None):
    """Process arguments and call view_func."""
    mpc = ConnectClient(addr=mpd_host, port=mpd_port)
    mpc._listen_on_fifo()
    dynamic_headers = translate_dynamic_headers(dynamic_headers)
    kb = KeyBindings(bind, fifo=mpc.fifo)
    view_settings = views.ViewSettings(
        cmd, keybinds=kb, dynamic_headers=dynamic_headers, sort_field=sort)

    view_func(mpc, view_settings)


@mfpfdzfppffzy.command(short_help="find and display single tracks")
@generic_options
@click.option(
    '--dynamic-headers',
    type=click.Choice(['yes', 'no', 'category']),
    help='create headers from the search query or the displayed tag fields')
def find(cmd, mpd_host, mpd_port, bind, sort, dynamic_headers):
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
                  sort=sort, dynamic_headers=dynamic_headers)


@mfpfdzfppffzy.command(short_help="find and display specific tags")
@generic_options
@click.option('--dynamic-headers', type=click.Choice(['yes', 'no']),
              help='create headers from search query')
def list(cmd, mpd_host, mpd_port, bind, sort, dynamic_headers):
    """
    Display results from mpd's list command in a simple index view.

    \b
    Example queries:
    mfpfdzfppffzy list artist
    mfpfdzfppffzy list album artist Ampere
    """
    run_with_args(views.container_view, cmd,
                  mpd_host=mpd_host, mpd_port=mpd_port, bind=bind,
                  sort=sort, dynamic_headers=dynamic_headers)


if __name__ == '__main__':
    mfpfdzfppffzy()
