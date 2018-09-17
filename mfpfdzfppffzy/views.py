import os
import sys
import subprocess
import shlex
import re
import shutil
from copy import deepcopy
from .utils import coroutine

FZF_PROG_OPTS = ('-m', '--height=100%', '--inline-info')
FZF_DEFAULT_OPTS = shlex.split(os.getenv('FZF_DEFAULT_OPTS', default=''))
ARTIST_PREFIX_MATCHER = re.compile(r'^the (.+)', flags=re.IGNORECASE)


class ViewSettings():
    """
    A container for settings relevant to creating views.
    Returns string arguments for command and header in a processible tuple
    form.
    """
    def __init__(self, cmd, header=None, sort_key=None):
        self.cmd = cmd
        self.header_str = header or ''
        self.sort_key = sort_key

    @property
    def header(self):
        """Return header as tuple for use in Popen and the like."""
        return ('--header', self.header_str)

    @header.setter
    def header(self, cmd):
        """Pass str input for header to self.header_str."""
        self.header_str = cmd


class FilterView():
    """
    Create a view consisting of several views that progressively filter the
    selection. The most obvious example would be Artist->Album->Title.
    FilterView takes in a sequence of ViewSettings from which these views are
    created.
    When dynamic_headers is True, headers will be created based on the last
    selection for every view but the first. In this case, provided headers are
    ignored.
    """
    def __init__(self, mpc, views, dynamic_headers=None,
                 final_view='track_view'):
        # the caller must make sure that the sequence is appropriately ordered
        self.mpc = mpc
        self.views = views
        self.dynamic_headers = dynamic_headers
        self.final_view = final_view
        self.state = 0
        self.final_state = len(views)
        self.selections = {}  # selections of each state

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
            self.sel = container_view(self.mpc, view)
        else:
            # TODO: Exception handling here
            self.sel = getattr(
                sys.modules[__name__], self.final_view)(self.mpc, view)

    def append_filters_to_list(self, l):
        """Takes a list l and appends all selected filters to it."""
        for state, sel in self.selections.items():
            l.append(self.views[state].cmd[0])
            l.append(sel)

    def get_adapted_view(self):
        """
        Create a copy of the current view. Update the header dynamically and
        add filters to the command.
        """
        view = deepcopy(self.active_view)
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
            if self.sel is None:
                self.move_backward()
            else:
                self.move_forward()

    def get_filtered_selection(self):
        """Get a list of items based on the selected filters."""
        filters_cmd = []
        self.append_filters_to_list(filters_cmd)
        return self.mpc.find(*filters_cmd)


def get_track_output_line(find_dict, *args):
    """
    Create a formatted line from find_dict including track number and
    title. Additional args will be ignored but are allowed for compatibility
    with add_entries_to_list.
    """
    return '{:02} - {}'.format(
        lax_int(find_dict['track']), find_dict['title'])


def get_formatted_output_line(*args):
    """
    Create an output line with each value in args receiving equal space of
    the terminal.
    """
    okay_w, _ = shutil.get_terminal_size()
    # fzf needs some columns for the margin
    okay_w -= 4
    # define a min_width here so things don't fall apart -  if the terminal is
    # THIS small, everything's gonna look like shit anyway
    min_w = len(args) * 4
    okay_w = okay_w if okay_w >= min_w else min_w
    item_w = int(okay_w / len(args))

    # there should be at least one space between (table) columns for better
    # optics (that's where the (item_w -1) comes in)
    output = map(
        lambda x: '{}…'.format(x[:item_w - 2]) if len(x) > (item_w - 1) else x,
        args)
    # pad if necessary and join
    output = ''.join([x.ljust(item_w) for x in output])
    return output


def get_tag_output_line(find_dict, *tags):
    """Create an output line from tags of find_dict."""
    find_tags = (find_dict[t] for t in tags)
    return get_formatted_output_line(*find_tags)


@coroutine
def add_entry_to_dict(entry_func, *entry_func_args):
    """
    Yield a dictionary from a find result. Passes this dictionary along with
    entry_func_args to entry_func to generate an output string and add this
    string to the dictionary with the key 'fzf_string'.
    """
    while True:
        find_entry = yield
        find_entry['fzf_string'] = entry_func(find_entry, *entry_func_args)


def add_entries_to_list(find_list, entry_func, entry_func_args):
    """
    Use entry_func with entry_func_args to create a custom entry for each dict
    in find_dict.
    """
    adder = add_entry_to_dict(entry_func, *entry_func_args)
    for d in find_list:
        adder.send(d)
    adder.close()


def adapt_duplicates(find_list):
    """Make sure the fzf_str key of each item in find_list is unique by
    appending NUL."""

    while True:
        fzf_strs = [x['fzf_str'] for x in find_list]
        dups = filter(lambda x: fzf_strs.count(x['fzf_str']) > 1, find_list)
        try:
            d = next(dups)
            d['fzf_str'] += '\u0000'
        except StopIteration:
            break


def pipe_to_fzf(content, *args):
    """Pipe content to fzf and return a tuple (stdout, stderr)."""
    fzf = subprocess.Popen(['fzf', *FZF_DEFAULT_OPTS, *FZF_PROG_OPTS, *args],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           encoding='utf-8')

    # TODO: exception handling
    stdout, stderr = fzf.communicate(input=content)
    return stdout, fzf.returncode


def create_view(items, *args, sort_key=None):
    """
    Create a fzf view from items. Additional args are passed to
    fzf. Optionally supply a sort_key for items. Returns the selected entry or
    None if selection was cancelled.
    """
    view = '\n'.join(sorted(set(items), key=sort_key))
    sel, returncode = pipe_to_fzf(view, *args)
    if returncode == 0:
        return sel.strip('\n')
    else:
        return None


def create_view_with_custom_entries(items, entry_func, *args,
                                    entry_func_args=None, sort_key=None):
    """
    Use entry func to add a custom entry to items which will be used by fzf
    to display entries. items must be an mpd find return list. Returns the
    track dict whose entry was selected.
    """
    entry_func_args = entry_func_args or []
    add_entries_to_list(items, entry_func, entry_func_args)
    entries = (x['fzf_string'] for x in items)
    sel = create_view(entries, *args, sort_key=sort_key)

    # pull selected dict out of list; return None if nothing was selected
    try:
        sel = next(filter(lambda x: x['fzf_string'] == sel, items))
        return sel
    except StopIteration:
        return None


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


def container_view(mpc, view_settings):
    """
    Use args to build a view that refers to another underlying view (such as
    a list of artists or albums). Return the selection.
    """
    entries = mpc.list(*view_settings.cmd)
    return create_view(entries, *view_settings.header,
                       sort_key=view_settings.sort_key)


def track_view(mpc, view_settings):
    """
    Use args to build a view listing tracks with their track
    numbers.
    Optionally specify sorting with sort_key and a header for fzf.
    Return the selection.
    """
    tracks = mpc.find(*view_settings.cmd, required_tags=['track', 'title'])
    return create_view_with_custom_entries(
        tracks, get_track_output_line, *view_settings.header,
        sort_key=view_settings.sort_key)


def singles_view(mpc, view_settings):
    """
    Use args as commands to the MPD Client and build a track-based view.

    The sort_key argument here applies to the string that is being handed over
    to fzf, which has the format 'Artist | Album | Title'.
    """
    tags = ['artist', 'album', 'title']
    singles = mpc.find(*view_settings.cmd, required_tags=tags)
    return create_view_with_custom_entries(
        singles, get_tag_output_line, *view_settings.header,
        entry_func_args=tags, sort_key=view_settings.sort_key)
