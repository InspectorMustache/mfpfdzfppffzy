import mfpfdzfppffzy.views as views


def test_view_settings():
    header = 'this is a test header'
    vs = views.ViewSettings(
        ['pseudo', 'command'],
        header
    )
    assert len(vs.header) == 2
    assert vs.header[0] == '--header'
    assert vs.header[1] == header
