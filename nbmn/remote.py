"""Remote access for movie data.

Once upon a time we used Rotten Tomatoes and their IMDB lookup. Since they no
longer allow free data access we have completely migrated to the Open Movie
DB at omdbapi.com (they accept donations if you are so inclined.)

One day we plan on switching to their Poster API as donors.

Any format described below as 'date' is in the format "%d %b %Y" and
assumes en_US locale

As a result, we have also redesigned the remote movie data that we return to
use the OMDB format:
{
    'Actors': 'comma delimited string',
    'Awards': 'string',  // short description of number
    'BoxOffice': '?',
    'Country': 'string',
    'DVD': 'date',
    'Director': 'comma delimited string',
    'Genre': 'comma delimited string',
    'Language': 'comma delimited string',
    'Metascore': 'int',
    'Plot': 'string',
    'Poster': 'URL',
    'Production': 'string', // production company
    'Rated': 'string', // mpaa rating
    'Released': 'date',
    'Response': 'boolean',  // True if no errors
    'Runtime': 'string',  // Generally of format 'n mins' where n is an int
    'Title': 'string',
    'Type': 'string',   // movie, episode, or series
    'Website': 'URL',  // Assumed - never seen
    'Writer': 'comma delimited string',  //Include credit type (story, screenplay, etc)
    'Year': 'int',  // 4 digit year

    'imdbID': 'string',  // in tt+int format
    'imdbRating': 'float',  // 0-10 floating point
    'imdbVotes': 'int', // positive

    'tomatoConsensus': 'string',  //generated
    'tomatoFresh': 'int', // fresh count
    'tomatoImage': 'string',  //image descrip, NOT URL
    'tomatoMeter': 'int',  //RT meter 1-100
    'tomatoRating': 'float',  //RT rating 1-10
    'tomatoReviews': 'int',
    'tomatoRotten': 'int', // rotten count
    'tomatoURL': 'URL',  //link to RT page
    'tomatoUserMeter': 'int',  //1-100
    'tomatoUserRating': 'float', //1-10
    'tomatoUserReviews': 'int'  //count
}

Many of the fields might contain "N/A" (Not Applicable).
"""

# pylama:ignore=E501

from datetime import datetime
import requests


def norm_imdbid(iid):
    """Return a normalized IMDB ID.

    Our current is to break down the ID to an int and then return the
    default format - a zero-padded 7 digit int pre-padded with 'tt'.
    """
    s = str(iid).strip().lower().lstrip('t').lstrip('0') if iid else ''
    if not s:
        return ''
    return "tt%07d" % int(s)


def get_movie_data(imdbid):
    """Retrieve movie data from remote sources.

    Currently this is just the OMDB API format.
    """
    imdbid = norm_imdbid(imdbid)
    if not imdbid:
        return dict()

    return {
        "update_time": str(datetime.now()),
        "omdb": omdb_get(imdbid)
    }


# Simple mapper from omdbapi.com to the format we expect from rot tom
# in imdb format
def omdb_get(omdb_id):
    """Perform OMDB GET and add any special xforms we support."""
    omdb_id = norm_imdbid(omdb_id)
    if not omdb_id:
        return dict()

    resp = requests.get("http://www.omdbapi.com/", params={
        'i':        omdb_id,
        'r':        'json',
        'tomatoes': 'true',
        'plot':     'short',
    }).json()

    if resp.get("Response", "").lower() != "true":
        return dict()

    # potentially comma-separated fields become lists
    for k in ['Actors', 'Director', 'Genre', 'Language', 'Writer']:
        v = resp.get(k, '')
        if not type(v) is list:
            v = str(v).strip()
            if not v or v.upper() == "N/A":
                v = []
            else:
                v = v.split(',')
        resp[k] = v

    # Best effort on numbers
    NUMERICS = [
        ('Metascore',         int),
        ('Year',              int),
        ('imdbRating',        float),
        ('imdbVotes',         int),
        ('tomatoFresh',       int),
        ('tomatoMeter',       int),
        ('tomatoRating',      float),
        ('tomatoReviews',     int),
        ('tomatoRotten',      int),
        ('tomatoUserMeter',   int),
        ('tomatoUserRating',  float),
        ('tomatoUserReviews', int),
    ]
    for k, func in NUMERICS:
        v = resp.get(k, None)
        if v:
            try:
                v = func(v)
            except:
                v = "NaN"
            resp[k] = v

    return resp
