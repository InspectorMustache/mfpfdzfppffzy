import re

PROG_NAME = 'MPD'
MFP_BIND_RE = re.compile(r'^mfp\((.*)\)$', flags=re.DOTALL)


class KeyBindings(dict):
    """
    Subclass of a dict whose string representation conforms to fzf's
    keybinding syntax.
    """

    def __init__(self, fifo):
        self.fifo = fifo
        self.custom_dict = {}
        self.cmd_temp = 'echo {} {{}} > ' + self.fifo
        self.exec_temp = 'execute#{}#'
        super().__init__()

    def __setitem__(self, key, value):
        """Adapt keybinds if they are wrapped in mfp()."""
        # do nothing if this is an empty key or empty command
        if not value.replace('&&', '').strip() or not key.strip():
            return

        match = MFP_BIND_RE.match(value)
        if match:
            mfp_cmd = match.group(1)

            if '&&' in mfp_cmd:
                value = self.get_multi_cmd(mfp_cmd)
            else:
                value = self.cmd_temp.format(mfp_cmd)

        self.custom_dict[key] = self.exec_temp.format(value)

    def get_multi_cmd(self, s):
        """
        Create a command for execute() made of multiple commands in s separated
        by '&&'.
        """
        cmds = [s.strip() for s in s.split('&&')]
        cmds = map(lambda x: self.cmd_temp.format(x), cmds)
        return ' && '.join(cmds)

    def items(self):
        return self.custom_dict.items()

    def __getitem__(self, key):
        return self.custom_dict[key]

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
