from random import randrange

from hypothesis import given
import hypothesis.strategies as st
import mfpfdzfppffzy.views as views
from pytest import fixture

MPD_FIND_RETURN_DICT = {'file': st.text(),
                        'last-modified': st.text(),
                        'time': st.text(),
                        'duration': st.text(),
                        'artist': st.text(),
                        'albumartist': st.text(),
                        'artistsort': st.text(),
                        'title': st.text(),
                        'album': st.text(),
                        'track': st.text(),
                        'date': st.text(),
                        'genre': st.text()}


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
        items = list(items)
        try:
            return items[randrange(0, len(items))], 0
        except ValueError:
            return '', 1

    monkeypatch.setattr(views, 'create_view', fake_create_view)


def is_find_return(ret):
    """Assert that ret is a single dict as returned by ConnectClient.find."""
    if ret:
        assert isinstance(ret, dict)
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
    st.lists(st.fixed_dictionaries(MPD_FIND_RETURN_DICT)))
def test_custom_view(viewsettings, find_return):
    sel = views.singles_view(monkey_mpc(find_return), viewsettings)
    is_find_return(sel)
