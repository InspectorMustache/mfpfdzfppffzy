import os
import shlex
import tempfile
import atexit
import logging
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
            raise UserError("The MPD server returned: {}".format(str(e)))

    return wrapped


def decorate_mpd_command(instance, f):
    """Return cmd decorated with always_connect and catch_command_error."""
    return always_connect(instance, catch_command_error(f))


def add_required_tags(f):
    """
    Ensure required tags for find and search based commands by decoration.
    """

    @wraps(f)
    def wrapped(self, *args, **kwargs):
        # make sure we get all the tags we need so we don't get a key error
        self.required_tags = kwargs.pop("required_tags", False)
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
        self.view = None  # these are for communication
        self.fifo = self.get_fifo()  # with fzf
        self.fifo_thread = None
        atexit.register(os.remove, self.fifo)
        super().__init__()
        self.ensure_connect()

    def get_fifo(self):
        """Create fifo in temp directory."""
        while True:
            try:  # this should be safer, right?
                path = tempfile.mktemp(prefix="mfpfdzfppffzy.")
                os.mkfifo(path)
                break
            except FileExistsError:
                continue

        return path

    def get_fifo_logger(self):
        """
        Create and return a logger that keeps track of commands sent to the
        fifo.
        """
        logger = logging.getLogger("fifo_log")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler("{}.log".format(self.fifo))
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s | %(message)s", datefmt="%H:%M:%S"
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        atexit.register(os.remove, "{}.log".format(self.fifo))

        return logger

    def receive_from_fifo(self):
        """
        Reads commands from self.fifo and parses them. Stops when NULL is
        received. This should only be run in parallel to the main application,
        so it's probably better to run self.listen_on_fifo().
        """
        fifo_logger = self.get_fifo_logger()

        while True:
            fifo_logger.info("waiting for message")
            with open(self.fifo) as fifo:
                msg = fifo.read()
                msg = msg.strip("\n")
                fifo_logger.info("received: {}".format(msg))

                try:
                    self.run_mpd_command(shlex.split(msg))
                except UserError as exc:
                    fifo_logger.warning("a UserError was raised: {}".format(exc))

    def listen_on_fifo(self):
        """
        Run a thread that continuously receivs data from the fifo by calling
        receive_from_fifo.
        """
        self.fifo_thread = Thread(target=self.receive_from_fifo, daemon=True)
        self.fifo_thread.start()

    def ensure_tags(self, title):
        """Ensure title has tags as keys."""
        for tag in filter(lambda x: x not in title.keys(), self.required_tags):
            title[tag] = ""
        return title

    def ensure_connect(self):
        """
        Wrap all mpd commands with the decorate_mpd_command (pseudo-)decorator.
        """
        # make initial connection for using the commands method
        self.connect()

        # filter out unavailable commands returned by commands(); I think this
        # is a bug with the mpd2 library
        for method_name in filter(lambda x: x in dir(self), self.commands()):
            method = getattr(self, method_name)
            setattr(self, method_name, decorate_mpd_command(self, method))

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

    def handle_view_settings(self, view_settings, *args, **kwargs):
        """Run a command associated with a ViewSettings object."""
        try:
            return getattr(self, view_settings.cmd)(
                *view_settings.cmd_args, *args, **view_settings.cmd_kwargs, **kwargs
            )
        except AttributeError:
            # this function should never be called with a non-registered method
            # as a command; a ViewSettings object should only be created with a
            # specific associated ConnectClient method in mind
            # otherwise the command should have been passed directly to the mpd
            # server and no ViewSettings object should have been created
            raise NotImplementedError

    def run_mpd_command(self, cmd_list):
        """
        Take in list cmd_list and parse it as an mpd command. Raise UserError
        if it's not a valid mpd command.
        """
        try:
            cmd = cmd_list[0]
            return getattr(self, cmd)(*cmd_list[1:])
        except AttributeError:
            raise UserError(
                '"{}" is not a valid mpd command.'.format(" ".join(cmd_list))
            )
