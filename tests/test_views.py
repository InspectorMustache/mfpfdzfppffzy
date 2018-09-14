import re
import shutil
import hypothesis.strategies as st
import mfpfdzfppffzy.views as views
from copy import copy
from random import randrange
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


def monkey_mpc(want_return):
    """
    Return a ConnectClient class instance whose find and list methods just
    return want_return. (Not really monkeypatching, this is just passed instead
    of a real ConnectClient instance).
    """
    class FakeConnectClient():
        def __init__(self, *args, **kwargs):
            pass

        def find(self, *args, **kwargs):
            return want_return

        def list(self, *args, **kwargs):
            return want_return

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
            return items[randrange(0, len(items))]
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


@given(st.lists(elements=st.text()), st.text())
def test_view_settings_header(cmd, header):
    vs = views.ViewSettings(cmd, header=header)
    assert len(vs.header) == 2
    assert vs.header[0] == '--header'
    assert vs.header[1] == header


@given(
    st.builds(
        views.ViewSettings, st.lists(elements=st.text()), header=st.text()),
    st.lists(elements=st.fixed_dictionaries(MPD_FIND_RETURN_DICT)),
    st.lists(st.text()))
def test_custom_view(viewsettings, find_return, list_return):
    sel = views.container_view(monkey_mpc(list_return), viewsettings)
    assert isinstance(sel, (str, NoneType))

    mpc_find = monkey_mpc(find_return)
    sel = views.singles_view(mpc_find, viewsettings)
    is_find_return(sel)

    sel = views.track_view(mpc_find, viewsettings)
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


@given(st.text())
def test_duplicate_handling(dup_text):
    find_dict = MPD_FIND_RETURN_DICT
    find_dict['fzf_str'] = dup_text

    # if it works with 4, it should work with any number of duplicates
    dups = []
    for _ in range(4):
        d = copy(find_dict)
        dups.append(d)

    views.adapt_duplicates(dups)
    fzf_strs = [x['fzf_str'] for x in dups]
    assert len(fzf_strs) == len(set(fzf_strs))
