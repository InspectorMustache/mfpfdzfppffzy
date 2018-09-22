import re
import shutil
import random
import hypothesis.strategies as st
import mfpfdzfppffzy.views as views
from copy import copy, deepcopy
from hypothesis import given
from pytest import fixture

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


def monkey_mpc(find_return=None, list_return=None):
    """
    Return a ConnectClient class instance whose find and list methods just
    return want_return. (Not really monkeypatching, this is just passed instead
    of a real ConnectClient instance).
    """
    class FakeConnectClient():
        def __init__(self, *args, **kwargs):
            self.find_return = find_return
            self.list_return = list_return

        def find(self, *args, **kwargs):
            return self.find_return

        def list(self, *args, **kwargs):
            return self.list_return

    return FakeConnectClient()


@fixture(autouse=True)
def monkey_create_view(monkeypatch):
    """
    Override create_view so that it just returns a random item from the item
    list it's passed.
    """

    def fake_create_view(items, *args, sort_key=None):
        items = tuple(items)
        try:
            return items[random.randrange(0, len(items))]
        except ValueError:
            return None

    monkeypatch.setattr(views, 'create_view', fake_create_view)


def is_find_return(ret):
    """Assert that ret is a single dict as returned by ConnectClient.find."""
    assert isinstance(ret, (dict, NoneType))
    if ret:
        for key in ('file', 'last-modified', 'time', 'duration', 'artist',
                    'albumartist', 'artistsort', 'title', 'album', 'track',
                    'date', 'genre'):
            assert key in ret


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
    st.builds(views.ViewSettings, st.lists(elements=st.text())),
    st.lists(elements=st.fixed_dictionaries(MPD_FIND_RETURN_DICT)),
    st.lists(st.text()))
def test_custom_view(viewsettings, find_return, list_return):
    mpc = monkey_mpc(list_return=list_return)
    sel = views.container_view(mpc, viewsettings)
    assert isinstance(sel, (str, NoneType))

    mpc.find_return = find_return
    sel = views.singles_view(mpc, viewsettings)
    is_find_return(sel)

    sel = views.track_view(mpc, viewsettings)
    is_find_return(sel)


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
    find_dict['fzf_str'] = dup_text

    # if it works with 4, it should work with any number of duplicates
    dups = []
    for _ in range(4):
        d = copy(find_dict)
        dups.append(d)

    views.adapt_duplicates(dups)
    fzf_strs = [x['fzf_str'] for x in dups]
    assert len(fzf_strs) == len(set(fzf_strs))


# TODO: test with min_size = 0 once this works
@given(st.lists(elements=st.fixed_dictionaries((MPD_FIND_RETURN_DICT)),
                min_size=1))
def test_filter_view(library):
    # build views from every mpd tag
    view_list = [views.ViewSettings([x]) for x in MPD_FIND_RETURN_DICT]
    mpc = monkey_mpc()
    filter_view = views.FilterView(mpc, view_list, dynamic_headers=True)

    list_returns = {}
    for index, view in enumerate(view_list):
        view_filter = view.cmd[0]
        # the view_filter value of every dict in library is a possible
        # selection so pick one at random
        return_value = random.choice(
            tuple(map(lambda x: x[view_filter], library)))
        list_returns[index] = return_value

    mpc.list_return = list_returns[filter_view.state]
    mpc.find_return = [random.choice(library)]

    # test going through all the views
    filter_view.pass_through()

    # this is a rather weak test because the find method is just overridden to
    # return any match from library
    # however without relying on an actual mpd database, I think this is the
    # best we've got
    for find_dict in filter_view.get_filtered_selection():
        is_find_return(find_dict)
