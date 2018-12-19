import re
from .utils import coroutine

MFP_KB_RE = re.compile(r'^mfp\((.*)\)$', flags=re.DOTALL)
MFP_BIND_RE = re.compile(r'(?:^|,)([^:]+):(mfp\([^\)]*\))')


class KeyBindings():
    """
    Subclass of a dict whose string representation conforms to fzf's
    keybinding syntax.
    """

    def __init__(self, args, fifo=None):
        # base_args is an initial bind argument that can be passed as is to fzf
        self.fifo = fifo
        self.bind_dict = {}
        self.bind_tuple = None
        self.cmd_temp = 'echo {} > ' + self.fifo
        self.exec_temp = 'execute#{}#'
        self.populate_bind_tuple(args)
        super().__init__()

    def populate_bind_tuple(self, bind_str):
        """
        Parse the bind string and use it to populate the bind dict with fzf
        commands.
        """
        processor = self.process_bind()
        for b in re.split(r'(?<!\\),', bind_str):
            processor.send(b)

        processor.send(None)
        processor.close()
        # use the populated bind_dict to create bind_tuple
        pairs = tuple(':'.join(t) for t in self.bind_dict.items())

        if pairs:
            self.bind_tuple = ('--bind={}'.format(','.join(pairs)), )
        else:
            self.bind_tuple = ()

    @coroutine
    def process_bind(self):
        """
        Yield a binding and put it into the bind dict as a command that fzf can
        understand.
        """
        processor = self.process_match()
        while True:
            bind_str = yield
            if bind_str is None:
                processor.close()
                continue

            match = MFP_BIND_RE.match(bind_str)
            if match:
                processor.send(match)
            else:
                match = bind_str.split(':', maxsplit=1)
                try:
                    self.bind_dict[match[0]] = match[1]
                except IndexError:
                    # if it's not a valid keybinding, do nothing
                    continue

    @coroutine
    def process_match(self):
        """
        Yield a match group and inspect its command. If it's a chained command,
        adapt it accordingly.
        """
        while True:
            match = yield
            cmd = match.group(2)
            cmd = MFP_KB_RE.match(cmd).group(1)
            if '&&' in cmd:
                cmd = self.get_multi_cmd(cmd)
            else:
                cmd = self.cmd_temp.format(cmd)

            self.bind_dict[match.group(1)] = self.exec_temp.format(cmd)

    def get_multi_cmd(self, cmd_str):
        """
        Create a command for execute() made of multiple commands in cmd_str
        separated by '&&'.
        """
        cmds = [s.strip() for s in cmd_str.split('&&')]
        cmds = map(lambda x: self.cmd_temp.format(x), cmds)
        return ' && '.join(cmds)

    def parse_bind_args(self, args):
        """
        Parse provided args to the bind command and populate the dict with mfp
        specific commands. Return the rest of the string which can be directly
        passed to fzf.
        """
        for m in MFP_BIND_RE.finditer(args):
            self[m.group(1)] = m.group(2)
        return MFP_BIND_RE.sub('', args)

    def __getitem__(self, key):
        return self.bind_tuple[key]

    def __iter__(self):
        for item in self.bind_tuple:
            yield item

    def __len__(self):
        return len(self.bind_tuple)

    def __repr__(self):
        return repr(self.bind_tuple)
