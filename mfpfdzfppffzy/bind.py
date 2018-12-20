import re
from .utils import coroutine

MFP_BIND_RE = re.compile(r'^(.+?):mfp\((.*)\)$', flags=re.DOTALL)


class KeyBindings():
    """
    An object that's represented as a tuple which can be passed to a subprocess
    method as a command line parameter.
    """

    def __init__(self, args, fifo=None):
        self.fifo = fifo
        self.bind_list = []
        self.bind_tuple = None
        self.cmd_temp = 'echo {} > ' + self.fifo
        self.exec_temp = 'execute#{}#'
        self.populate_bind_list(args)

    def populate_bind_list(self, binds):
        """
        Parse the bind string and use it to populate bind_list with fzf
        commands.
        """
        processor = self.process_bind()
        for b in binds:
            processor.send(b)

        processor.send(None)
        processor.close()

        # use the populated bind_list to create bind_tuple
        if self.bind_list:
            self.bind_tuple = ('--bind={}'.format(','.join(self.bind_list)), )
        else:
            self.bind_tuple = ()

    @coroutine
    def process_bind(self):
        """
        Yield a binding and put it into bind_list as a command that fzf can
        understand.
        """
        processor = self.process_mfp()
        while True:
            bind_str = yield
            if bind_str is None:
                processor.close()
                continue

            if MFP_BIND_RE.match(bind_str):
                processor.send(bind_str)
            else:
                self.bind_list.append(bind_str)

    @coroutine
    def process_mfp(self):
        """
        Yield a bind string and inspect its command. If it's a chained command,
        adapt it accordingly.
        """
        while True:
            bind_str = yield
            key, cmd = MFP_BIND_RE.match(bind_str).groups()

            if '&&' in cmd:
                cmd = self.get_multi_cmd(cmd)
            else:
                cmd = self.cmd_temp.format(cmd)

            cmd = self.exec_temp.format(cmd)
            self.bind_list.append('{}:{}'.format(key, cmd))

    def get_multi_cmd(self, cmd_str):
        """
        Create a command for execute() made of multiple commands in cmd_str
        separated by '&&'.
        """
        cmds = [s.strip() for s in cmd_str.split('&&')]
        cmds = map(lambda x: self.cmd_temp.format(x), cmds)
        return ' && '.join(cmds)

    def __getitem__(self, key):
        return self.bind_tuple[key]

    def __iter__(self):
        for item in self.bind_tuple:
            yield item

    def __len__(self):
        return len(self.bind_tuple)

    def __repr__(self):
        return repr(self.bind_tuple)
