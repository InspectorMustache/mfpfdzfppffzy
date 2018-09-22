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

# constants for the three types of dynamic headers
NO_DYNAMIC_HEADERS = 0
DYNAMIC_HEADERS = 1
CAT_DYNAMIC_HEADERS = 2


class ViewSettings():
    """
    A container for settings relevant to creating views.
    Returns string arguments for command and header in a processible tuple
    form.
    """
    def __init__(self, cmd, sort_field=None, the_sort=False,
                 keybinds=None, dynamic_headers=NO_DYNAMIC_HEADERS):
        self.cmd = cmd
        self.the_sort = the_sort  # include/don't include "the" when sorting
        self.sort_field = sort_field
        self.keybinds = keybinds
        self.dynamic_headers = dynamic_headers
        self.header_str = ''

    @property
    def header(self):
        """Return header as tuple for use in Popen and the like."""
        return ('--header', self.header_str) if self.header_str else ()

    @header.setter
    def header(self, value):
        """Pass str input for header to self.header_str."""
        self.header_str = value

    def update_headers(self, *args):
        """
        Create headers with args based on whether dynamic headers are enabled
        or not.
        """
        if self.dynamic_headers == DYNAMIC_HEADERS:
            self.header_str = self.cmd[-1].capitalize()
        elif self.dynamic_headers == CAT_DYNAMIC_HEADERS and args:
            self.header_str = get_formatted_output_line(
                *[x.capitalize() for x in args])


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
    in find_dict. Make sure there are no duplicates afterwards.
    """
    adder = add_entry_to_dict(entry_func, *entry_func_args)
    for d in find_list:
        adder.send(d)

    adder.close()
    adapt_find_duplicates(find_list)


def adapt_find_duplicates(find_list):
    """Make sure the fzf_string key of each item in find_list is unique by
    appending NUL."""

    while True:
        fzf_strs = [x['fzf_string'] for x in find_list]
        dups = filter(lambda x: fzf_strs.count(x['fzf_string']) > 1, find_list)
        try:
            d = next(dups)
            d['fzf_string'] += '\u0000'
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


def create_view(items, *args):
    """
    Create a fzf view from items. Additional args are passed to
    fzf. Returns the selected entry or None if selection was cancelled.
    """
    view = '\n'.join(items)
    sel, returncode = pipe_to_fzf(view, *args)
    if returncode == 0:
        return sel.strip('\n')
    else:
        return None


def create_plain_view(items, view_settings):
    """Create a view from str_list with sorting it first."""
    key_func = make_sort_function(sort_field=view_settings.sort_field,
                                  the_sort=view_settings.the_sort)
    items.sort(key=key_func)
    create_view(items, *view_settings.header)


def create_view_with_custom_entries(items, entry_func, view_settings,
                                    entry_func_args=()):
    """
    Use entry func to add a custom entry to items which will be used by fzf
    to display entries. items must be an mpd find return list. Returns the
    track dict whose entry was selected.
    """
    add_entries_to_list(items, entry_func, entry_func_args)
    entries = [x['fzf_string'] for x in items]
    key_func = make_sort_function(sort_field=view_settings.sort_field,
                                  the_sort=view_settings.the_sort)
    entries.sort(key=key_func)
    sel = create_view(entries, *view_settings.header)

    # pull selected dict out of list; return None if nothing was selected
    # TODO: this probably isn't needed here, for stdout it should be enough if
    # the selection is echoed
    try:
        sel = next(filter(lambda x: x['fzf_string'] == sel, items))
        return sel
    except StopIteration:
        return None


def make_sort_function(sort_field=None, the_sort=False):
    """
    Make a sort key function. If sort_field is provided, the structure to be
    sorted is assumed to be a find dict and sort_field will be used for
    sorting. Otherwise the structure is assumed to be a simple list of
    strings. the_sort controls whether or not a prepending 'The' is ignored or
    not.
    """
    if not the_sort:
        if sort_field:
            return lambda x: x[sort_field]
        else:
            return lambda x: x.lower()
    else:
        if sort_field:
            def key_sort(x):
                mo = ARTIST_PREFIX_MATCHER.match(x[sort_field])
                return mo.group(1).lower() if mo else x[sort_field].lower()
        else:
            def key_sort(x):
                mo = ARTIST_PREFIX_MATCHER.match(x)
                return mo.group(1).lower() if mo else x.lower()
        return key_sort


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
    view_settings.update_headers()
    return create_plain_view(entries, view_settings)


def track_view(mpc, view_settings):
    """
    Use args to build a view listing tracks with their track
    numbers.
    Optionally specify sorting with sort_field and a header for fzf.
    Return the selection.
    """
    tracks = mpc.find(*view_settings.cmd, required_tags=['track', 'title'])
    view_settings.update_headers()
    return create_view_with_custom_entries(
        tracks, get_track_output_line, view_settings)


def singles_view(mpc, view_settings):
    """
    Use args as commands to the MPD Client and build a track-based view.
    """
    tags = ('artist', 'album', 'title')
    singles = mpc.find(*view_settings.cmd, required_tags=tags)
    view_settings.update_headers(*tags)
    return create_view_with_custom_entries(
        singles, get_tag_output_line, view_settings,
        entry_func_args=tags)
