import os
import mpd
from .utils import notify
from functools import wraps

try:
    MPD_PORT = int(os.getenv("MPD_PORT", default=6600))
except ValueError:
    # if MPD_PORT is set to something strange, fall back to 6600
    MPD_PORT = 6600

MPD_HOST = os.getenv('MPD_HOST', default="127.0.0.1")


def with_connection(f):
    """
    Decorator that connects and disconnects before and after running f.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            args[0].ping()
        except mpd.base.ConnectionError:
            args[0].connect()
        v = f(*args, **kwargs)
        args[0].close()
        return v

    return wrapped


class ConnectClient(mpd.MPDClient):
    """
    Derived MPDClient that checks for an existing connection on major methods.
    """

    def __init__(self):
        self.required_tags = False
        super().__init__()

    @with_connection
    def list(self, *args, **kwargs):
        return super().list(*args, **kwargs)

    @with_connection
    def find(self, *args, **kwargs):
        # make sure we get all the tags we need so we don't get a key error
        self.required_tags = kwargs.pop('required_tags', False)
        match = super().find(*args, **kwargs)

        if self.required_tags:
            return list(map(self.ensure_tags, match))
        else:
            return match

    def connect(self, *args, **kwargs):
        """
        Wrapper for the parent connect method that catches and notifies of
        Exceptions.
        """
        try:
            super().connect(MPD_HOST, *args, port=MPD_PORT, **kwargs)
        except (ConnectionRefusedError, TimeoutError):
            notify('Error connecting to MPD instance')

    def ensure_tags(self, title):
        """
        Ensure title has tags as keys.
        """
        for tag in (x for x in self.required_tags if x not in title.keys()):
            title[tag] = ''
        return title


MPD_C = ConnectClient()
