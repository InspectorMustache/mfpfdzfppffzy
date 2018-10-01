import re

# general program constants
PROG_NAME = 'MPD'
MPD_FIELDS = ('artist', 'artistsort', 'album', 'albumsort', 'albumartist',
              'albumartistsort', 'title', 'track', 'name', 'genre', 'date',
              'composer', 'performer', 'comment', 'disc',
              'musicbrainz_artistid', 'musicbrainz_albumid',
              'musicbrainz_albumartistid', 'musicbrainz_trackid',
              'musicbrainz_releasetrackid', 'musicbrainz_workid')

MFP_KB_RE = re.compile(r'^mfp\((.*)\)$', flags=re.DOTALL)
MFP_BIND_RE = re.compile(r'(?:^|,)([^:]+):(mfp\([^\)]*\))')


class KeyBindings(dict):
    """
    Subclass of a dict whose string representation conforms to fzf's
    keybinding syntax.
    """

    def __init__(self, args, fifo=None):
        # base_args is an initial bind argument that can be passed as is to fzf
        self.fifo = fifo
        self.custom_dict = {}
        self.cmd_temp = 'echo {} > ' + self.fifo
        self.exec_temp = 'execute#{}#'
        self.base_args = self.parse_bind_args(args) if args else None
        super().__init__()

    def parse_bind_args(self, args):
        """
        Parse provided args to the bind command and populate the dict with mfp
        specific commands. Return the rest of the string which can be directly
        passed to fzf.
        """
        for m in MFP_BIND_RE.finditer(args):
            self[m.group(1)] = m.group(2)
        return MFP_BIND_RE.sub('', args)

    def get_multi_cmd(self, s):
        """
        Create a command for execute() made of multiple commands in s separated
        by '&&'.
        """
        cmds = [s.strip() for s in s.split('&&')]
        cmds = map(lambda x: self.cmd_temp.format(x), cmds)
        return ' && '.join(cmds)

    def __setitem__(self, key, value):
        """Adapt keybinds if they are wrapped in mfp()."""
        # do nothing if this is an empty key/command
        if not value.replace('&&', '').strip() or not key.strip():
            return

        match = MFP_KB_RE.match(value)
        if match:
            mfp_cmd = match.group(1)

            if '&&' in mfp_cmd:
                value = self.get_multi_cmd(mfp_cmd)
            else:
                value = self.cmd_temp.format(mfp_cmd)

        self.custom_dict[key] = self.exec_temp.format(value)

    def __getitem__(self, key):
        return self.custom_dict[key]

    def __str__(self):
        pairs = [':'.join(t) for t in self.custom_dict.items()]
        if self.base_args:
            pairs.append(self.base_args)

        if pairs:
            return '--bind={}'.format(','.join(pairs))
        else:
            return ''


def coroutine(f):
    """Prime coroutine by calling next on it once."""
    def primed(*args, **kwargs):
        cr = f(*args, **kwargs)
        next(cr)
        return cr
    return primed
