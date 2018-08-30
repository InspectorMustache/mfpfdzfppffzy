import mpd
import os
import subprocess
import shlex
import re
import shutil
from functools import wraps

try:
    MPD_PORT = int(os.getenv("MPD_PORT", default=6600))
except ValueError:
    # if MPD_PORT is set to something strange, fall back to 6600
    MPD_PORT = 6600

MPD_HOST = os.getenv('MPD_HOST', default="127.0.0.1")
PROG_NAME = 'MPD'
FZF_PROG_OPTS = ['-m', '--height=100%', '--inline-info']
FZF_DEFAULT_OPTS = shlex.split(os.getenv('FZF_DEFAULT_OPTS', default=''))
ARTIST_PREFIX_MATCHER = re.compile(r'^the (.+)', flags=re.IGNORECASE)


class KeyBindings(dict):
    """Subclass of a dict whose string representation conforms to fzf's
      keybinding syntax."""

    def __init__(self):
        super().__init__()

    def __str__(self):
        pairs = (':'.join(t) for t in self.items())
        return '--bind={}'.format(','.join(pairs))


def with_connection(f):
    """Decorator that connects and disconnects before and after running f."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            args[0].ping()
        except mpd.base.ConnectionError:
            connect_to_mpd()
        return f(*args, **kwargs)
        args[0].close()

    return wrapped


class ConnectClient(mpd.MPDClient):
    """Derived MPDClient that checks for an existing connection on the major
    methods."""

    def __init__(self):
        self.required_tags = False
        super().__init__()

    @with_connection
    def list(self, *args, **kwargs):
        return super().list(*args, **kwargs)

    @with_connection
    def find(self, *args, **kwargs):
        # make sure we get all the tags we need so we don't get a key error
        self.required_tags = kwargs.pop('required_tags', False)
        match = super().find(*args, **kwargs)

        if self.required_tags:
            return list(map(self.ensure_tags, match))
        else:
            return match

    def ensure_tags(self, title):
        """Ensure title has tags as keys."""
        for tag in (x for x in self.required_tags if x not in title.keys()):
            title[tag] = ''
        return title


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


def get_output_line(*args):
    """Create an output line with each value in args receiving equal space of
    the terminal."""
    okay_w, _ = shutil.get_terminal_size()
    # fzf needs some columns for the margin
    okay_w -= 4
    item_w = int(okay_w / len(args))

    # truncate if necessary
    # there should be at least one space between (table) columns for better
    # optics
    output = map(
        lambda x: '{}…'.format(x[:item_w - 2]) if len(x) > item_w else x,
        args)
    # pad if necessary and join
    output = '\u200c'.join([x.ljust(item_w) for x in output])
    return output


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
    fzf. Optionally supply a sort_key for items. Returns the output from fzf."""
    view = '\n'.join(sorted(set(items), key=sort_key))
    sel, _ = pipe_to_fzf(view, *args)
    return sel.strip('\n')


def artist_sorter(item):
    """Strip 'The' from artist and sort without case sensitivity."""
    mo = ARTIST_PREFIX_MATCHER.match(item)
    if mo:
        return mo.group(1).lower()
    else:
        return item.lower()


def lax_int(x):
    """Try integer conversion or just return 0."""
    try:
        return int(x)
    except ValueError:
        return 0


def library_view():
    """Browse through artist, album, track in this order."""
    artist_sel = create_view(
        mpd_c.list('artist'), sort_key=artist_sorter)

    album_sel = create_view(
        mpd_c.list('album', 'artist', artist_sel), '--header', artist_sel)

    tracks = mpd_c.find('artist', artist_sel, 'album', album_sel,
                        required_tags=['track', 'title'])
    # create a list of formatted strings from the list of dicts we got
    tracks = ('{:02} - {}'.format(lax_int(x['track']), x['title'])
              for x in tracks)
    track_sel = create_view(tracks, '--header', '{} - {}'.format(artist_sel,
                                                                 album_sel))


def singles_view(*args):
    """Use args as commands to the MPD Client and build a track-based view."""
    mpd_return = mpd_c.find(*args,
                            required_tags=['artist', 'album', 'title'])
    singles = (get_output_line(x['artist'], x['title'], x['album'])
               for x in mpd_return)
    header = get_output_line('Artist', 'Title', 'Album')
    single_sel = create_view(singles, '--header', header)
    print(single_sel)


mpd_c = ConnectClient()
library_view()
