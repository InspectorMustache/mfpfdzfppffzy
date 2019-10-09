from mfpfdzfppffzy.bind import KeyBindings
from hypothesis import given
from hypothesis.strategies import text


def get_kb_str(keybind, mfp_cmd=None, fifo=None):
    """Create a string for testing keybinds from the provided parameters."""
    return "{}:execute-silent#echo {} > {} &#".format(keybind, mfp_cmd, fifo)


def text_filter(x):
    """Filter function for keybindings text input."""
    for c in ("&&", ",", ")"):
        if c in x:
            return False
    return True


@given(text().filter(text_filter), text().filter(text_filter))
def test_key_bindings(mfp_cmd1, mfp_cmd2):
    # I trust that tempfile.mktemp doesn't create files with quotes in them...?
    fifo = "/some/path with a a space/somewhere"
    fzf_bind_args = "ctrl-a:mfp(y-1),ctrl-b:x-1,ctrl-c:mfp(y-2),ctrl-d:x-2"
    kb = KeyBindings(fzf_bind_args, fifo=fifo)
    # {} should be addable by the user and not cause any problems
    mfp_cmd1 += " {}"

    # a KeyBindings object should always be a tuple with a single string
    # element
    assert len(kb) == 1
    assert type(*kb) is str
    assert kb[0][0:7] == "--bind="

    # test keybinds created by initiation
    assert "ctrl-b:x-1" in kb[0]
    assert "ctrl-d:x-2" in kb[0]
    assert get_kb_str("ctrl-a", mfp_cmd="y-1", fifo=fifo) in kb[0]
    assert get_kb_str("ctrl-c", mfp_cmd="y-2", fifo=fifo) in kb[0]

    # test conversion of single commands
    fzf_bind_args += ",ctrl-e:mfp({})".format(mfp_cmd1)
    fzf_bind_args += ",ctrl-f:mfp({})".format(mfp_cmd2)

    kb = KeyBindings(fzf_bind_args, fifo=fifo)
    assert get_kb_str("ctrl-e", mfp_cmd=mfp_cmd1, fifo=fifo) in kb[0]
    assert get_kb_str("ctrl-f", mfp_cmd=mfp_cmd2, fifo=fifo) in kb[0]

    # test conversion of multiple commands
    mfp_chained = " && ".join([mfp_cmd1, mfp_cmd2])
    fzf_bind_args += ",ctrl-g:mfp({})".format(mfp_chained)
    kb = KeyBindings(fzf_bind_args, fifo=fifo)
    assert (
        "ctrl-g:execute-silent#echo {0} > {2} && echo {1} > {2} &#".format(
            mfp_cmd1.strip(), mfp_cmd2.strip(), fifo
        )
        in kb[0]
    )

    # finally assert that str(KeyBindings) will output nothing if there are no
    # keybindings
    kb = KeyBindings("", fifo="")
    assert len(kb) == 0
