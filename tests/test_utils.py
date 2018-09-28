from mfpfdzfppffzy.utils import KeyBindings
from hypothesis import given
from hypothesis.strategies import text


def get_kb_str(keybind, mfp_cmd=None, fifo=None):
    """Create a string for testing keybinds from the provided parameters."""
    return '{}:execute#echo {} {{}} > {}#'.format(keybind, mfp_cmd, fifo)


@given(text().filter(lambda x: '&&' not in x),
       text().filter(lambda x: '&&' not in x))
def test_key_bindings(mfp_cmd1, mfp_cmd2):
    # I trust that tempfile.mktemp doesn't create files with quotes in them...?
    fifo = '/some/path with a a space/somewhere'
    fzf_bind_args = 'ctrl-a:mfp(y-1),ctrl-b:x-1,ctrl-c:mfp(y-2),ctrl-d:x-2'
    kb = KeyBindings(fzf_bind_args, fifo=fifo)

    # test keybinds created by initiation
    assert 'ctrl-b:x-1,ctrl-d:x-2' in str(kb)
    assert get_kb_str('ctrl-a', mfp_cmd='y-1', fifo=fifo) in str(kb)
    assert get_kb_str('ctrl-c', mfp_cmd='y-2', fifo=fifo) in str(kb)

    # test conversion of single commands
    kb['ctrl-e'] = 'mfp({})'.format(mfp_cmd1)
    kb['ctrl-f'] = 'mfp({})'.format(mfp_cmd2)

    assert get_kb_str('ctrl-e', mfp_cmd=mfp_cmd1, fifo=fifo) in str(kb)
    assert get_kb_str('ctrl-f', mfp_cmd=mfp_cmd2, fifo=fifo) in str(kb)

    # test conversion of multiple commands
    kb = KeyBindings(fzf_bind_args, fifo=fifo)
    mfp_chained = ' && '.join([mfp_cmd1, mfp_cmd2])
    kb['ctrl-g'] = 'mfp({})'.format(mfp_chained)
    assert 'ctrl-g:execute#echo {0} {{}} > {2} && echo {1} {{}} > {2}#'.format(
        mfp_cmd1.strip(), mfp_cmd2.strip(), fifo) in str(kb)
