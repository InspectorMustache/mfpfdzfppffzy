import mpd
import os
import subprocess
import shlex
import re
from functools import wraps

try:
    MPD_PORT = int(os.getenv("MPD_PORT", default=6600))
except ValueError:
    # if MPD_PORT is set to something strange, fall back to 6600
    MPD_PORT = 6600

MPD_HOST = os.getenv('MPD_HOST', default="127.0.0.1")
PROG_NAME = 'MPD'
FZF_PROG_OPTS = ['-m', '--height=100%', '--layout', 'default', '--inline-info']
FZF_DEFAULT_OPTS = shlex.split(os.getenv('FZF_DEFAULT_OPTS', default=''))
ARTIST_PREFIX_MATCHER = re.compile(r'^the (.+)', flags=re.IGNORECASE)


def with_connection(f):
    """Decorator that connects and disconnects before and after running f."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            args[0].ping()
        except mpd.base.ConnectionError:
            connect_to_mpd()
        # breakpoint()
        return f(*args, **kwargs)
        args[0].close()

    return wrapped


class ConnectClient(mpd.MPDClient):
    """Derived MPDClient that checks for an existing connection on the major
    methods."""

    def __init__(self):
        super().__init__()

    @with_connection
    def list(self, *args, **kwargs):
        return super().list(*args, **kwargs)

    @with_connection
    def find(self, *args, **kwargs):
        return super().find(*args, **kwargs)


def connect_to_mpd():
    """Connect the global client instance to the mpd server."""
    try:
        mpd_c.connect(MPD_HOST, port=MPD_PORT)
    except (ConnectionRefusedError, TimeoutError):
        notify('Error connectiog to MPD instance')


def notify(msg):
    """Try using notify-send to display a notification. If there is no
    notify-send command, do nothing."""
    try:
        subprocess.run(['notify-send', PROG_NAME, msg])
    except FileNotFoundError:
        pass


def pipe_to_fzf(content, *args):
    """Pipe content to fzf and return a tuple containing (stdout, stderr)."""
    fzf = subprocess.Popen(['fzf', *FZF_DEFAULT_OPTS, *FZF_PROG_OPTS, *args],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           encoding='utf-8')

    try:
        ret = fzf.communicate(input=content)
        if fzf.returncode == 130:
            exit()
        else:
            return ret
    except Exception:  # yes yes, bad I know
        notify('Error running fzf')


def create_view(items, *args, sort_key=None):
    """Create a fzf view from items. Additional args are passed to
    fzf. Optionally supply a sort_key to sort items. Return the selection from
    fzf."""
    view = '\n'.join(sorted(set(items), key=sort_key))
    (sel, _) = pipe_to_fzf(view, *args)
    return sel.strip('\n')


def artist_sorter(item):
    """Strip 'The' from artist and sort without case sensitivity."""
    mo = ARTIST_PREFIX_MATCHER.match(item)
    if mo:
        return mo.group(1).lower()
    else:
        return item.lower()


def library_mode():
    """Browse through artist, album, track in this order."""
    artist_sel = create_view(mpd_c.list('artist'), sort_key=artist_sorter)
    album_sel = create_view(mpd_c.list('album', 'artist', artist_sel),
                            '--header', artist_sel)
    tracks = ['{:02} - {}'.format(int(x['track']), x['title'])
              for x in mpd_c.find('artist', artist_sel, 'album', album_sel)]
    track_sel = create_view(tracks, '--header', '{} - {}'.format(
        artist_sel, album_sel))
    print(track_sel)


mpd_c = ConnectClient()
library_mode()
