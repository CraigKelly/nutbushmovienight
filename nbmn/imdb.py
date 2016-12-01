"""IMDB helper functions.

This is a "core" module - it shouldn't import from anywhere else.
"""

# pylama:ignore=E501,D213


def norm_imdbid(iid):
    """Return a normalized IMDB ID.

    Our current is to break down the ID to an int and then return the
    default format - a zero-padded 7 digit int pre-padded with 'tt'.
    """
    s = str(iid).strip().lower().lstrip('t').lstrip('0') if iid else ''
    if not s:
        return ''
    return "tt%07d" % int(s)
