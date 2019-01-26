import re
import shutil
import random
import hypothesis.strategies as st
import mfpfdzfppffzy.views as views
from copy import copy
from hypothesis import given
from pytest import fixture
from mfpfdzfppffzy.cli import mfp_cmds

# we only need the names of the mfp commands
mfp_cmds = tuple(mfp_cmds.keys())
# NoneType for use with isinstance() as part of a tuple
NoneType = type(None)

TRACK_FORMAT_RX = re.compile(r'^\d{2,} - .+$', flags=re.DOTALL)
SPACE_RX = re.compile(r'\s+')
TAG_RX = re.compile(r'\A\S+\Z')
# text size for each value is at least one because we mpc.find() has been
# called with the correct require_tags argument
MPD_FIND_RETURN_DICT = {'file': st.from_regex(TAG_RX),
                        'last-modified': st.from_regex(TAG_RX),
                        'time': st.from_regex(TAG_RX),
                        'duration': st.from_regex(TAG_RX),
                        'artist': st.from_regex(TAG_RX),
                        'albumartist': st.from_regex(TAG_RX),
                        'artistsort': st.from_regex(TAG_RX),
                        'title': st.from_regex(TAG_RX),
                        'album': st.from_regex(TAG_RX),
                        'track': st.from_regex(TAG_RX),
                        'date': st.from_regex(TAG_RX),
                        'genre': st.from_regex(TAG_RX)}
MPD_COMMANDS = {'cleartagid', 'clearerror', 'findadd', 'replay_gain_status',
                'channels', 'find', 'unsubscribe', 'swapid', 'list',
                'toggleoutput', 'notcommands', 'listmounts', 'lsinfo',
                'listplaylistinfo', 'search', 'replay_gain_mode', 'listall',
                'plchanges', 'config', 'clear', 'previous', 'consume',
                'commands', 'listfiles', 'seek', 'playid', 'pause', 'idle',
                'mount', 'add', 'addtagid', 'rm', 'mixrampdelay', 'random',
                'searchadd', 'rename', 'swap', 'delete', 'currentsong',
                'moveid', 'kill', 'playlistclear', 'subscribe', 'rangeid',
                'seekcur', 'playlistmove', 'update', 'enableoutput',
                'urlhandlers', 'listplaylists', 'playlistdelete', 'prioid',
                'crossfade', 'addid', 'playlistid', 'password', 'readmessages',
                'playlistfind', 'play', 'move', 'playlistsearch', 'deleteid',
                'sendmessage', 'searchaddpl', 'listallinfo', 'playlist',
                'playlistinfo', 'repeat', 'plchangesposid', 'setvol', 'load',
                'stop', 'stats', 'next', 'ping', 'playlistadd', 'prio',
                'outputs', 'listplaylist', 'count', 'disableoutput', 'single',
                'save', 'close', 'decoders', 'mixrampdb', 'shuffle', 'seekid',
                'readcomments', 'rescan', 'status', 'tagtypes'}


def monkey_mpc(find_return=None, list_return=None):
    """
    Return a ConnectClient class instance whose find, search and list methods
    just return the specified return value. (Not really monkeypatching, this is
    just passed instead of a real ConnectClient instance).
    """
    class FakeConnectClient():
        def __init__(self, *args, **kwargs):
            self.find_return = find_return
            self.list_return = list_return

        def find(self, *args, **kwargs):
            return self.find_return

        def search(self, *args, **kwargs):
            return self.find_return

        def list(self, *args, **kwargs):
            return self.list_return

        def handle_view_settings(self, view_settings, *args, **kwargs):
            return getattr(
                self, view_settings.cmd)(
                    *view_settings.cmd_args, *args, **kwargs)

    return FakeConnectClient()


@fixture(autouse=True)
def monkey_create_view(monkeypatch):
    """
    Override create_view so that it just returns a random item from the item
    list it's passed.
    """

    def fake_create_view(view_settings, *args):
        entries = tuple(view_settings.entries)
        try:
            return entries[random.randrange(0, len(entries))]
        except ValueError:
            return None

    monkeypatch.setattr(views, 'create_view', fake_create_view)


def is_find_return_sel(ret):
    """Assert that ret is a single dict as returned by ConnectClient.find."""
    assert isinstance(ret, (dict, NoneType))
    if ret:
        for key in ('file', 'last-modified', 'time', 'duration', 'artist',
                    'albumartist', 'artistsort', 'title', 'album', 'track',
                    'date', 'genre'):
            assert key in ret


def get_cmd_strategy(include_mfp=False, mfp_only=False):
    """
    Create a strategy which generates list where the first item is
    one of the supported mfp_commands. Include custom defined mfpfdzfppffzy
    commands if include_mfp is True.
    """
    if include_mfp and mfp_only:
        raise TypeError('include_mfp and mfp_only are mutually exclusive.')
    elif include_mfp:
        cmds = list(MPD_COMMANDS | set(mfp_cmds))
    elif mfp_only:
        cmds = list(mfp_cmds)
    else:
        cmds = list(MPD_COMMANDS)

    base_cmd_st = st.sampled_from(cmds)
    return base_cmd_st.flatmap(get_cmd_flatmap)


def get_cmd_flatmap(base):
    l_st = st.lists(elements=st.text())
    return l_st.map(lambda x: [base] + x)


@given(st.lists(elements=st.text(min_size=1), min_size=1),
       st.lists(elements=st.text(min_size=1), min_size=1))
def test_view_settings_header(cmd, tags):
    vs = views.ViewSettings(cmd)
    assert not vs.header
    vs.dynamic_headers = views.NO_DYNAMIC_HEADERS
    vs.update_headers()
    assert not vs.header

    vs.dynamic_headers = views.DYNAMIC_HEADERS
    vs.update_headers()
    assert len(vs.header) == 2
    assert vs.header[0] == '--header'

    vs.header_str = ''
    vs.dynamic_headers = views.CAT_DYNAMIC_HEADERS
    vs.update_headers(*tags)
    assert len(vs.header) == 2
    assert vs.header[0] == '--header'


@given(
    get_cmd_strategy(mfp_only=True),
    st.lists(elements=st.fixed_dictionaries(MPD_FIND_RETURN_DICT), min_size=1),
    st.lists(st.text()))
def test_custom_view(cmd, find_return, list_return):
    viewsettings = views.ViewSettings(cmd)
    viewsettings.cmd = 'list'
    mpc = monkey_mpc(list_return=list_return, find_return=find_return)
    sel = views.container_view(mpc, viewsettings)
    assert isinstance(sel, (str, NoneType))

    # create a new ViewSettings instance so we get a fresh entries field
    viewsettings = views.ViewSettings(cmd)
    viewsettings.cmd = 'find'
    sel = views.singles_view(mpc, viewsettings)
    is_find_return_sel(sel)

    viewsettings = views.ViewSettings(cmd)
    viewsettings.cmd = 'search'
    sel = views.track_view(mpc, viewsettings)
    is_find_return_sel(sel)


@given(st.fixed_dictionaries(MPD_FIND_RETURN_DICT),
       st.sets(
           min_size=1, max_size=len(MPD_FIND_RETURN_DICT),
           elements=st.sampled_from(tuple(MPD_FIND_RETURN_DICT.keys()))),
       st.integers(min_value=1, max_value=300))
def test_string_constructors(monkeypatch, find_dict, tags, term_size):
    track_str = views.get_track_output_line(find_dict)
    assert isinstance(track_str, str)
    assert TRACK_FORMAT_RX.match(track_str)

    monkeypatch.setattr(shutil, 'get_terminal_size', lambda: (term_size, 0))

    tag_str = views.get_tag_output_line(find_dict, *tags)
    assert isinstance(tag_str, str)
    assert len(tag_str.split()) == len(list(tags))


@given(st.text(), st.fixed_dictionaries(MPD_FIND_RETURN_DICT))
def test_duplicate_handling(dup_text, find_dict):
    find_dict['fzf_string'] = dup_text

    # if it works with 4, it should work with any number of duplicates
    dups = []
    for _ in range(4):
        d = copy(find_dict)
        dups.append(d)

    views.adapt_find_duplicates(dups)
    fzf_strs = [x['fzf_string'] for x in dups]
    assert len(fzf_strs) == len(set(fzf_strs))


@given(st.lists(elements=st.fixed_dictionaries((MPD_FIND_RETURN_DICT)),
                min_size=1))
def test_filter_view(library):
    # build views from every mpd tag
    view_list = []
    for tag in MPD_FIND_RETURN_DICT:
        vs = views.ViewSettings(
            [random.choice(mfp_cmds), tag])
        view_list.append(vs)

    mpc = monkey_mpc()
    filter_view = views.FilterView(mpc, view_list, dynamic_headers=True)

    list_returns = {}
    for index, view in enumerate(view_list):
        view_filter = view.cmd_args[0]
        # very difficult to do real testing here without reimplementing the mpd
        # library - so just return a list of all values of the provided tag for
        # mpc.list
        return_value = [x[view_filter] for x in library]
        list_returns[index] = return_value

    mpc.list_return = list_returns[filter_view.state]
    mpc.find_return = [random.choice(library)]

    # test going through all the views
    filter_view.pass_through()

    # this is a rather weak test because the find method is overridden to just
    # return any match from library
    # however without relying on an actual mpd database, I think this is the
    # best we've got
    for find_dict in filter_view.get_filtered_selection():
        is_find_return_sel(find_dict)


@given(st.lists(elements=st.fixed_dictionaries((MPD_FIND_RETURN_DICT))))
def test_sorting(find_list):
    list_list = [x['artist'] for x in find_list]
    vs = views.ViewSettings(['dummy', 'command'], sort_field='artist')

    # sort list of find dicts
    sorted_find_list = sorted(find_list, key=vs.sort_func)

    # sort list of list entries
    vs.out_type = str
    sorted_list_list = sorted(list_list, key=vs.sort_func)
    check_list = [x['artist'] for x in sorted_find_list]
    assert check_list == sorted_list_list

    # sort with 'the' stripping
    for d in find_list:
        d['artist'] = 'The {}'.format(d['artist'])

    vs.the_sort = True
    vs.out_type = dict
    sorted_find_list_the = sorted(find_list, key=vs.sort_func)
    check_list_no_the = [x['time'] for x in sorted_find_list]
    check_list_the = [x['time'] for x in sorted_find_list_the]
    assert check_list_no_the == check_list_the
