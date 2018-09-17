from subprocess import run
import re

PROG_NAME = 'MPD'
MFP_BIND_RE = re.compile(r'^mfp\((.+)\)$')


class KeyBindings(dict):
    """
    Subclass of a dict whose string representation conforms to fzf's
    keybinding syntax.
    """

    def __init__(self, fifo):
        self.fifo = fifo
        super().__init__()

    def __setitem__(self, key, value):
        """Adapt keybinds if they are wrapped in mfp()."""
        match = MFP_BIND_RE.match(value)
        if match:
            self[key] = 'execute#echo {} {{}} > {}#'.format(
                match.group(1), self.fifo)
        else:
            self[key] = value

    def __str__(self):
        pairs = (':'.join(t) for t in self.items())
        return '--bind={}'.format(','.join(pairs))


def coroutine(f):
    """Prime coroutine by calling next on it once."""
    def primed(*args, **kwargs):
        cr = f(*args, **kwargs)
        next(cr)
        return cr
    return primed
