# general program constants
PROG_NAME = "MPD"
MPD_FIELDS = (
    "artist",
    "artistsort",
    "album",
    "albumsort",
    "albumartist",
    "albumartistsort",
    "title",
    "track",
    "name",
    "genre",
    "date",
    "composer",
    "performer",
    "comment",
    "disc",
    "musicbrainz_artistid",
    "musicbrainz_albumid",
    "musicbrainz_albumartistid",
    "musicbrainz_trackid",
    "musicbrainz_releasetrackid",
    "musicbrainz_workid",
)


def coroutine(f):
    """Prime coroutine by calling next on it once."""

    def primed(*args, **kwargs):
        cr = f(*args, **kwargs)
        next(cr)
        return cr

    return primed


class UserError(BaseException):
    """
    Raise in place of other exceptions for errors expectable from user input.
    """

    pass


def lax_int(x):
    """
    Try integer conversion or just return 0.
    """
    try:
        return int(x)
    except ValueError:
        return 0
