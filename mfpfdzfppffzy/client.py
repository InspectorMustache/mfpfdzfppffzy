import os
import shlex
import tempfile
import atexit
import mpd
from threading import Thread
from functools import wraps
from .utils import UserError


def always_connect(instance, f):
    """
    Decorator that makes sure there is a connection to mpd before running f.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        v = None
        timeout = 0
        while v is None:
            try:
                v = f(*args, **kwargs)
                break
            except mpd.base.ConnectionError as e:
                if timeout > 5:
                    raise e
                else:
                    instance.connect()
                    timeout += 1
        return v

    return wrapped


def catch_command_error(f):
    """Decorator that catches CommandErrors and reraises them as UserErrors."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except mpd.CommandError as e:
            raise UserError('The MPD server returned: {}'.format(str(e)))

    return wrapped


def decorate_command(instance, f):
    """Return cmd decorated with always_connect and catch_command_error."""
    return always_connect(instance, catch_command_error(f))


def add_required_tags(f):
    """
    Ensure required tags for find and search based commands by decoration.
    """
    @wraps(f)
    def wrapped(self, *args, **kwargs):
        # make sure we get all the tags we need so we don't get a key error
        self.required_tags = kwargs.pop('required_tags', False)
        match = f(self, *args, **kwargs)

        if self.required_tags:
            return list(map(self.ensure_tags, match))
        else:
            return match

    return wrapped


class ConnectClient(mpd.MPDClient):
    """Derived MPDClient with some helper methods added."""

    def __init__(self, host, port=None):
        self.required_tags = False
        self.addr = host
        self.port = port
        self.view = None                # these are for communication
        self.fifo = self._get_fifo()    # with fzf
        self.fifo_thread = None
        super().__init__()
        self.ensure_connect()

    def _get_fifo(self):
        """Create fifo in temp directory."""
        while True:
            try:  # this should be safer, right?
                path = tempfile.mktemp(prefix='mfpfdzfppffzy.')
                os.mkfifo(path)
                break
            except FileExistsError:
                continue

        atexit.register(os.remove, path)
        return path

    def _receive_from_fifo(self):
        """
        Reads commands from self.fifo and parses them. Stops when NULL is
        received. This should only be run in parallel to the main application,
        so it's probably better to run self._listen_on_fifo().
        """
        while True:
            with open(self.fifo) as fifo:
                msg = fifo.read()
                if msg.strip('\n') == 'NULL':
                    break

                self.mfp_run_command(msg.strip('\n'))

    def _listen_on_fifo(self):
        """
        Run a thread that continuously receivs data from the fifo by calling
        _receive_from_fifo.
        """
        self.fifo_thread = Thread(target=self._receive_from_fifo, daemon=True)
        self.fifo_thread.start()

    def _ensure_tags(self, title):
        """Ensure title has tags as keys."""
        for tag in filter(lambda x: x not in title.keys(), self.required_tags):
            title[tag] = ''
        return title

    def ensure_connect(self):
        """
        Wrap all mpd commands with the decorate_command (pseudo-)decorator.
        """
        # make initial connection for using the commands method
        self.connect()

        # filter out unavailable commands returned by commands(); I think this
        # is a bug with the mpd2 library
        for method_name in filter(lambda x: x in dir(self), self.commands()):
            method = getattr(self, method_name)
            setattr(self, method_name, decorate_command(self, method))

    def connect(self, *args, **kwargs):
        """Connect to mpd by using class fields."""
        try:
            super().connect(self.addr, *args, port=self.port, **kwargs)
        except ConnectionRefusedError:
            raise UserError("Unable to establish connection to MPD server.")

    @add_required_tags
    def find(self, *args, **kwargs):
        return super().find(*args, **kwargs)

    @add_required_tags
    def search(self, *args, **kwargs):
        return super().search(*args, **kwargs)


    def run_mpd_command(self, cmd_list):
        """
        Take in list cmd_list and parse it as an mpd command. Raise UserError
        if it's not a valid mpd command.
        """
        try:
            cmd = cmd_list[0]
            return getattr(self, cmd)(*cmd_list[1:])
        except AttributeError:
            raise UserError('"{}" is not a valid mpd command.'.format(
                ' '.join(cmd_list)))
