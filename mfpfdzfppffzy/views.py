import os
import sys
import subprocess
import shlex
import re
import shutil
from copy import deepcopy
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
    def __init__(self, cmd, header=None, sort_key=None):
        self.cmd = cmd
        self.header_str = header or ''
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
    When dynamic_headers is True, headers will be created based on the last
    selection for every view but the first. In this case, provided headers are
    ignored.
    """
    def __init__(self, views, dynamic_headers=None, final_view='track_view'):
        # the caller must make sure that the list is appropriately ordered
        self.views = views
        self.dynamic_headers = dynamic_headers
        self.final_view = final_view
        self.state = 0
        self.final_state = len(views)
        self.returncode = 0  # last returned returncode
        self.selections = {}  # selections of each state
        self.filter_cmd = {}  # filters retrieved from each state

    @property
    def active_view(self):
        """The currently active view."""
        return self.views[self.state]

    @property
    def sel(self):
        """Shorthand for selection of current view."""
        return self.selections[self.state]

    @sel.setter
    def sel(self, sel):
        self.selections[self.state] = sel

    def move_forward(self):
        """Go to next view."""
        self.state += 1

    def move_backward(self):
        """Go back to previous view."""
        self.state -= 1

    def call_view_function(self):
        """Call appropriate view function. Container view for everything but
        the last view. For the last view, try track view first and fall back to
        container view."""
        view = self.get_adapted_view()

        if self.state < self.final_state - 1:
            self.sel, self.returncode = container_view(view)
        else:
            # TODO: Exception handling here
            breakpoint()
            getattr(sys.modules[__name__], self.final_view)(view)

    def append_filters_to_list(self, l):
        """Takes a list l and appends all selected filters to it."""
        for state, sel in self.selections.items():
            l.append(self.views[state].cmd[0])
            l.append(sel)

    def get_adapted_view(self):
        """
        Create a copy of the current view. Clean out empty command arguments,
        update the header dynamically and add filters to the command.
        """
        view = deepcopy(self.active_view)
        # clearing out empty commands
        try:
            view.cmd.remove('')
        except ValueError:
            pass
        # updating the header
        if self.dynamic_headers and self.state != 0:
            view.header = self.selections[self.state - 1]
        # adding filters
        self.append_filters_to_list(view.cmd)

        return view

    def pass_through(self):
        """Move through views until we reach the final one."""
        while self.state in range(0, self.final_state):
            self.call_view_function()
            if self.returncode == 0:
                self.move_forward()
            else:
                self.move_backward()

    def get_filtered_selection(self):
        """Get a list of items based on the selected filters."""
        filters_cmd = []
        self.append_filters_to_list(filters_cmd)
        return mpc.find(*filters_cmd)


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
        stdout, stderr = fzf.communicate(input=content)
        return stdout, fzf.returncode
    except Exception:  # yes yes, bad I know
        notify('Error running fzf')


def create_view(items, *args, sort_key=None):
    """
    Create a fzf view from items. Additional args are passed to
    fzf. Optionally supply a sort_key for items. Returns a tuple containing the
    output and returncode of the fzf command.
    """
    view = '\n'.join(sorted(set(items), key=sort_key))
    sel, returncode = pipe_to_fzf(view, *args)
    return (sel.strip('\n'), returncode)


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
    entries = mpc.list(*view_settings.cmd)
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
        *view_settings.cmd, required_tags=['track', 'title']
    ))

    return create_view(tracks, *view_settings.header,
                       sort_key=view_settings.sort_key)


def singles_view(view_settings):
    """
    Use args as commands to the MPD Client and build a track-based view.

    The sort_key argument here applies to the string that is being handed over
    to fzf, which has the format 'Artist | Album | Title'.
    """
    mpd_return = mpc.find(*view_settings.cmd,
                          required_tags=['artist', 'album', 'title'])
    singles = (get_output_line(x['artist'], x['title'], x['album'])
               for x in mpd_return)
    return create_view(singles, *view_settings.header,
                       sort_key=view_settings.sort_key)
