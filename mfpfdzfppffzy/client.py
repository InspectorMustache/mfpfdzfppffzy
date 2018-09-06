import os
import shlex
import mpd
from functools import wraps

try:
    MPD_PORT = int(os.getenv("MPD_PORT", default=6600))
except ValueError:
    # if MPD_PORT is set to something strange, fall back to 6600
    MPD_PORT = 6600

MPD_HOST = os.getenv('MPD_HOST', default="127.0.0.1")


def ensure_connect(f):
    """
    Decorator that makes sure there is a connection to mpd before running f.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        v = None
        while v is None:
            try:
                v = f(*args, **kwargs)
            except mpd.base.ConnectionError:
                args[0].connect()
        return v

    return wrapped


def always_connect(c):
    """Class decorator to deocrate all relevant methods in c with
    ensure_connection."""
    exclude = ['ping', 'connect', 'close']

    def filter_func(x):
        """
        Return True for attributes that should be decorated. This includes
        non-dunder methods that are not in exclude.
        """
        return all((x not in exclude,
                    not x.startswith('_'),
                    callable(getattr(c, x))))

    for method_name in filter(filter_func, dir(c)):
        method = getattr(c, method_name)
        setattr(c, method_name, ensure_connect(method))

    return c


@always_connect
class ConnectClient(mpd.MPDClient):
    """
    Derived MPDClient that checks for an existing connection on major methods.
    """

    def __init__(self, addr=MPD_HOST, port=MPD_PORT):
        self.required_tags = False
        self.addr = addr
        self.port = port
        super().__init__()

    def connect(self, *args, **kwargs):
        """
        Connect to mpd by using class fields.
        """
        super().connect(self.addr, *args, port=self.port, **kwargs)

    def list(self, *args, **kwargs):
        return super().list(*args, **kwargs)

    def find(self, *args, **kwargs):
        # make sure we get all the tags we need so we don't get a key error
        self.required_tags = kwargs.pop('required_tags', False)
        match = super().find(*args, **kwargs)

        if self.required_tags:
            return list(map(self._ensure_tags, match))
        else:
            return match

    def _ensure_tags(self, title):
        """
        Ensure title has tags as keys.
        """
        for tag in filter(lambda x: x not in title.keys(), self.required_tags):
            title[tag] = ''
        return title

    def mfp_run_command(self, cmd_str):
        """Take in string cmd and parse it as an mpd command. (mfp stands for
        our application name here)."""
        cmd_list = shlex.parse(cmd_str)
        try:
            cmd = cmd_list.pop(0)
            getattr(self, cmd)(*cmd_list)
        except (IndexError, AttributeError):
            raise mpd.base.CommandError(
                '{} is not a valid mpd command'.format(cmd_str)
            )


MPD_C = ConnectClient()
