"""Remote access for movie data.

We provide get_movie_data, which is a thin wrapper around the RT and OMDB API's
"""

# pylama:ignore=E501

import sys
import traceback
from urllib.parse import urlparse, urlunparse, parse_qs
from datetime import datetime

import requests

from .log import app_logger

MATER_API_KEY = ""  # Set for us on startup


def norm_imdbid(iid):
    """Return a normalized IMDB ID.

    Our current is to break down the ID to an int and then return the
    default format - a zero-padded 7 digit int pre-padded with 'tt'.
    """
    s = str(iid).strip().lower().lstrip('t').lstrip('0') if iid else ''
    if not s:
        return ''
    return "tt%07d" % int(s)


def _parse_url(url):
    """Return (url, qs) where qs is requests compatible dictionary."""
    if not url:
        return None, None
    parse = urlparse(url)
    new_url = urlunparse([
        parse.scheme,
        parse.netloc,
        parse.path,
        parse.params,
        '',
        parse.fragment
    ])
    qs = dict([
        (key, vallist[0] if vallist else '')
        for key, vallist in parse_qs(parse.query).items()
    ])
    return new_url, qs


# MUTATES imdb_json
def _fix_directors(imdb_json):
    """RT and OMDB sometimes mess up the abridged_directors field."""
    dirs = imdb_json.get('abridged_directors', list())
    dirmod = False
    for idx in range(len(dirs)):  # We modify the array
        d = dirs[idx]
        if isinstance(d, str):
            dirs[idx] = dict(name=d)
            dirmod = True
    # If we have changes, perform reset to a deep-ish copy
    if dirmod:
        imdb_json['abridged_directors'] = [dict(x) for x in dirs]


def get_movie_data(imdbid, use_rt=True):
    """Retrieve movie data from remote sources.

    Currently we start with rotten tomatoes and fall back to OMDB API.
    If use_rt is set to False (default is True), we will skip Rotten Tomatoes.
    This is generally useful when RT has the wrong IMDB cross reference.
    """
    imdbid = norm_imdbid(imdbid)
    if not imdbid:
        return dict()

    rt_success = None
    if use_rt:
        imdb_json = rt_get(imdbid)
        rt_err = imdb_json.get("error", "").strip()
        if rt_err:
            app_logger().info("Failed on RT query for %s - will try OMDB. Error was", imdbid, rt_err)
            rt_success = False
        else:
            app_logger().info("RT query succeed for %s", imdbid)
            rt_success = True
    else:
        app_logger().info("RT query skipped for %s - will try OMDB", imdbid)
        rt_success = False

    assert not (rt_success is None)
    if not rt_success:
        imdb_json = omdb_get(imdbid)

    # Make sure that the directors field is correct
    _fix_directors(imdb_json)

    return {
        "update_time": str(datetime.now()),
        "imdb": imdb_json,
        "rottom": rt_get_cast(imdb_json),
    }


def rt_get(imdbid):
    """Perform RT GET and return appropriate Python object."""
    try:
        return requests.get(
            "http://api.rottentomatoes.com/api/public/v1.0/movie_alias.json",
            params={
                "apikey": MATER_API_KEY,
                "type":   "imdb",
                "id":     imdbid.lstrip('t')  # RT doesn't like the proper tt prefix
            }
        ).json()
    except:
        etype, evalue, etrace = sys.exc_info()
        rt_err = traceback.format_exception(etype, evalue, etrace)
        return {"error": rt_err}


def rt_get_cast(rt_json):
    """Use RT to get cast information for a previous REST request."""
    try:
        cast_url = rt_json.get("links", {}).get("cast", None)
    except:
        cast_url = None

    cast_url, cast_params = _parse_url(cast_url)
    if cast_url:
        if not cast_params:
            cast_params = {}
        cast_params['apikey'] = MATER_API_KEY
        try:
            return requests.get(cast_url, params=cast_params).json()
        except:
            return {"error": "Could not get RT cast information"}


# Simple mapper from omdbapi.com to the format we expect from rot tom
# in imdb format
def omdb_get(omdb_id):
    """Perform OMDB ReST GET and map to RT/IMDB format."""
    omdb_id = norm_imdbid(omdb_id)
    if not omdb_id:
        return dict()

    omdb_json = requests.get(
        "http://www.omdbapi.com/",
        params={'i': omdb_id}
    ).json()

    if omdb_json.get("Response", "").lower() != "true":
        return dict()

    def g(fld):
        return omdb_json.get(fld, "").strip()

    def fake_rating(r):
        try:
            return int(float(r) * 10.0)
        except:
            return r

    return {
        "critics_consensus": "",
        "id": "",
        "link-template": "",
        "links": {},
        "studio": "",

        "mpaa_rating": g("Rated"),
        "release_dates": {"theatre": g("Released")},
        "runtime": g("Runtime"),
        "synopsis": g("Plot"),
        "year": g("Year"),
        "title": g("Title"),

        "abridged_cast": [
            {"characters": [], "id": "", "name": act} for act in g("Actors").split(",")
        ],

        "abridged_directors": [g("Director")],

        "alternate_ids": {"imdb": g("imdbID").strip("t")},

        "genres": [i.strip() for i in g("Genre").split(",")],

        "ratings": {
            "audience_rating": "(Faked from IMDb users * 10)",
            "audience_score": fake_rating(g("imdbRating"))
        },

        "posters": {"detailed": g("Poster")},
    }
