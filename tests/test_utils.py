from mfpfdzfppffzy.utils import KeyBindings


def test_key_bindings():
    fifo = '/tmp/bla'
    kb = KeyBindings(fifo)

    keysym = 'ctrl-p'
    mfp_cmd = 'do this'
    kb[keysym] = 'mfp({})'.format(mfp_cmd)
    assert '{}:execute#echo {} {{}} > {}#'.format(
        keysym, mfp_cmd, fifo) in str(kb)
