import click
from . import views
from .client import ConnectClient


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


def get_mpc_from_context(ctx):
    """
    Return a ConnectClient instance created from settings held in the click
    context.
    """
    return ConnectClient(addr=ctx.obj[0], port=ctx.obj[1])


@click.group()
@click.option('--mpd-host', envvar='MPD_HOST', default='127.0.0.1',
              help='Address of a remote or local mpd server')
@click.option('--mpd-port', envvar='MPD_PORT', default=6600,
              help='Port address of a remote or local mpd server')
@click.pass_context
def mfp(ctx, mpd_host, mpd_port):
    """Browse the mpd library with fzf."""
    ctx.obj = (mpd_host, mpd_port)


@mfp.command()
@click.argument('cmd', nargs=-1, required=True)
@click.option('--bind')
@click.option('--dynamic-headers',
              type=click.Choice(['yes', 'no', 'category']))
@click.pass_context
def singles(ctx, cmd, bind, dynamic_headers):
    """Use a three-pane listing"""
    mpc = get_mpc_from_context(ctx)
    dynamic_headers = translate_dynamic_headers(dynamic_headers)
    view_settings = views.ViewSettings(cmd, dynamic_headers=dynamic_headers)
    views.singles_view(mpc, view_settings)


@mfp.command()
@click.argument('cmd', nargs=-1, required=True)
@click.option('--bind')
@click.option('--dynamic-headers',
              type=click.Choice(['yes', 'no']))
@click.pass_context
def tracks(ctx, cmd, bind, dynamic_headers):
    """List tracks by track number and song title"""
    mpc = get_mpc_from_context(ctx)
    dynamic_headers = translate_dynamic_headers(dynamic_headers)
    view_settings = views.ViewSettings(cmd, dynamic_headers=dynamic_headers)
    views.track_view(mpc, view_settings)


if __name__ == '__main__':
    mfp()
