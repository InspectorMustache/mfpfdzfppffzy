from mfpfdzfppffzy.utils import KeyBindings
from hypothesis import given
from hypothesis.strategies import text

@given(text().filter(lambda x: '&&' not in x),
       text().filter(lambda x: '&&' not in x))
def test_key_bindings(mfp_cmd1, mfp_cmd2):
    fifo = '/some/path/somewhere'
    kb = KeyBindings(fifo)

    # test conversion of single commands
    kb['ctrl-a'] = 'mfp({})'.format(mfp_cmd1)
    kb['ctrl-b'] = 'mfp({})'.format(mfp_cmd2)

    assert 'ctrl-a:execute#echo {} {{}} > {}#'.format(mfp_cmd1, fifo) in str(kb)
    assert 'ctrl-b:execute#echo {} {{}} > {}#'.format(mfp_cmd2, fifo) in str(kb)

    # test conversion of multiple commands
    kb = KeyBindings(fifo)
    mfp_chained = ' && '.join([mfp_cmd1, mfp_cmd2])
    kb['ctrl-c'] = 'mfp({})'.format(mfp_chained)
    assert 'ctrl-c:execute#echo {0} {{}} > {2} && echo {1} {{}} > {2}#'.format(
        mfp_cmd1.strip(), mfp_cmd2.strip(), fifo) in str(kb)
