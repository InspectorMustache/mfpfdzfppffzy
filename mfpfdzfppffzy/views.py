import os
import subprocess
import shlex
import re
import shutil
from .utils import notify
from .client import MPD_C as mpc

FZF_PROG_OPTS = ['-m', '--height=100%', '--inline-info']
FZF_DEFAULT_OPTS = shlex.split(os.getenv('FZF_DEFAULT_OPTS', default=''))
ARTIST_PREFIX_MATCHER = re.compile(r'^the (.+)', flags=re.IGNORECASE)


class ViewSettings():
    """
    A container for settings relevant to creating views.
    Returns string arguments for command and header in a processible list form.
    """
    def __init__(self, command, header=None, sort_key=None):
        self.command = command
        self.header_str = header
        self.sort_key = sort_key

    @property
    def header(self):
        """Return header as list for use in Popen and the like."""
        return ['--header', self.header_str]

    @header.setter
    def header(self, cmd):
        """Pass str input for header to self.header_str."""
        self.header_str = cmd


class KeyBindings(dict):
    """Subclass of a dict whose string representation conforms to fzf's
      keybinding syntax."""

    def __init__(self):
        super().__init__()

    def __str__(self):
        pairs = (':'.join(t) for t in self.items())
        return '--bind={}'.format(','.join(pairs))


class FilterView():
    """
    Create a view consisting of several views that progressively filter the
    selection. The most obvious example would be Artist->Album->Title.
    FilterView takes in a list of ViewSettings from which these views are
    created.
    """
    def __init__(self, views):
        # the caller must make sure that the list is appropriately ordered
        self.views = views
        self.state = 0
        self.end_state = len(views) + 1
        self.filter = {x.command[0]: '' for x in views[1:]}

    def pass_through(self):
        """Move through views until we reach the final one. Return final
        selection."""
        while True:
            active_view = self.views[self.state]

            if self.state is not self.end_state:
                sel = container_view(active_view)
            else:
                sel = track_view(active_view)

            self.state = self.state + 1 if sel else self.state

            if self.state == self.end_state or self.state == 0:
                break


def get_track_line(track_dict):
    """
    Create a formatted line from track_dict including track number and title.
    """
    return '{:02} - {}'.format(
        lax_int(track_dict['track']), track_dict['title']
    )


def get_output_line(*args):
    """
    Create an output line with each value in args receiving equal space of
    the terminal.
    """
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
    """
    Pipe content to fzf and return a tuple containing (stdout, stderr).
    """
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
    """
    Create a fzf view from items. Additional args are passed to
    fzf. Optionally supply a sort_key for items. Returns the output from
    fzf.
    """
    view = '\n'.join(sorted(set(items), key=sort_key))
    sel, _ = pipe_to_fzf(view, *args)
    return sel.strip('\n')


def artist_sorter(item):
    """
    Strip 'The' from artist and sort without case sensitivity.
    """
    mo = ARTIST_PREFIX_MATCHER.match(item)
    if mo:
        return mo.group(1).lower()
    else:
        return item.lower()


def lax_int(x):
    """
Try integer conversion or just return 0.
    """
    try:
        return int(x)
    except ValueError:
        return 0


def container_view(view_settings):
    """
    Use args to build a view that refers to another underlying view (such as
    a list of artists or albums). Optionally specify sorting with sort_key.
    Return the selection.
    """
    entries = mpc.list(*view_settings.command)
    return create_view(entries, *view_settings.header,
                       sort_key=view_settings.sort_key)


def track_view(view_settings):
    """
    Use args to build a view listing tracks with their track
    numbers.
    Optionally specify sorting with sort_key and a header for fzf.
    Return the selection.
    """
    # create a list of nicely formatted strings from the list of dicts we got
    # from mpd
    tracks = (get_track_line(x) for x in mpc.find(
        *view_settings.command, required_tags=['artist', 'album', 'title']
    ))

    return create_view(tracks, *view_settings.header,
                       sort_key=view_settings.sort_key)


def singles_view(view_settings):
    """
    Use args as commands to the MPD Client and build a track-based view.

    The sort_key argument here applies to the string that is being handed over
    to fzf, which has the format 'Artist | Album | Title'.
    """
    mpd_return = mpc.find(*view_settings.command,
                          required_tags=['artist', 'album', 'title'])
    singles = (get_output_line(x['artist'], x['title'], x['album'])
               for x in mpd_return)
    return create_view(singles, *view_settings.header,
                       sort_key=view_settings.sort_key)
