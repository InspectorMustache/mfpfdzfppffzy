from subprocess import run

PROG_NAME = 'MPD'


def notify(msg):
    """
    Try using notify-send to display a notification. If there is no
    notify-send command, do nothing.
    """
    try:
        run(['notify-send', PROG_NAME, msg])
    except FileNotFoundError:
        pass
